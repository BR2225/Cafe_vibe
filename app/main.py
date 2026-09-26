import hashlib
import hmac
import io
import logging
import os
import secrets
import uuid
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import segno  # noqa: E402
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from . import ai, recommend  # noqa: E402
from .db import Admin, CafeTable, Event, MenuItem, Order, SessionLocal, Visit, get_setting, init_db, set_setting, utcnow  # noqa: E402
from .seed import demo_items  # noqa: E402

log = logging.getLogger("cafe")
BASE = Path(__file__).resolve().parent
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")
SECRET = os.getenv("SECRET_KEY", ADMIN_PIN)
DEFAULT_CAFE_NAME = os.getenv("CAFE_NAME", "Brew & Co.")


# ---------- setup ----------

def ensure_embeddings(db):
    missing = db.scalars(select(MenuItem).where(MenuItem.embedding.is_(None))).all()
    if missing:
        vecs = ai.embed([ai.item_text(i) for i in missing])
        for item, v in zip(missing, vecs):
            item.embedding = v
        db.commit()


def remove_items(db, items):
    """Delete menu items together with their tap history."""
    ids = [i.id for i in items]
    if ids:
        db.execute(delete(Event).where(Event.item_id.in_(ids)))
        for i in items:
            db.delete(i)
        db.flush()


def add_items(db, drafts):
    for d in drafts:
        db.add(MenuItem(
            name=d["name"].strip()[:120],
            description=(d.get("description") or "").strip(),
            price=d.get("price"),
            category=(d.get("category") or "Other").strip()[:60],
            veg=bool(d.get("veg", True)),
            allergens=[a.strip().lower() for a in d.get("allergens") or [] if a.strip()],
            tags=[t.strip().lower() for t in d.get("tags") or [] if t.strip()],
            blurb=(d.get("blurb") or "").strip(),
        ))
    db.commit()
    ensure_embeddings(db)


@asynccontextmanager
async def lifespan(app):
    init_db()
    with SessionLocal() as db:
        try:
            if not db.scalar(select(func.count(CafeTable.id))):
                for n in range(1, 7):
                    db.add(CafeTable(number=n, seats=2 if n <= 2 else 4, token=new_token()))
                db.commit()
            if not db.scalar(select(func.count(MenuItem.id))):
                add_items(db, demo_items())
            else:
                ensure_embeddings(db)
        except Exception:
            log.exception("Menu seeding/embedding failed; will retry on demand")
    yield


app = FastAPI(title="Café Companion", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.globals["currency"] = os.getenv("CURRENCY", "₹")


def get_db():
    with SessionLocal() as db:
        yield db


def cafe_name(db):
    return get_setting(db, "cafe_name", DEFAULT_CAFE_NAME)


def all_items(db):
    return db.scalars(select(MenuItem).order_by(MenuItem.category, MenuItem.name)).all()


# ---------- customer helpers ----------

def current_visit(request: Request, db) -> Visit:
    vid = request.cookies.get("visit")
    visit = db.get(Visit, vid) if vid else None
    if not visit:
        raise HTTPException(401, "Scan the table QR code to start")
    visit.last_seen = utcnow()
    return visit


def popular_ids(db) -> set[int]:
    since = utcnow() - timedelta(hours=24)
    rows = db.execute(
        select(Event.item_id, func.count()).where(Event.kind == "like", Event.created_at >= since, Event.item_id.isnot(None))
        .group_by(Event.item_id).having(func.count() >= 3)
    ).all()
    return {r[0] for r in rows}


def card(item, visit, menu, popular, score=None):
    return {
        "id": item.id, "name": item.name, "price": item.price, "category": item.category,
        "description": item.description, "blurb": item.blurb, "veg": item.veg,
        "allergens": item.allergens or [], "tags": item.tags or [], "available": item.available,
        "reason": recommend.reason(item, visit, menu, popular),
        "reaction": (visit.reactions or {}).get(str(item.id)),
        "score": score,
    }


def log_events(db, visit, kind, item_ids):
    for iid in item_ids:
        db.add(Event(visit_id=visit.id, item_id=iid, kind=kind))


def set_picks(db, visit, items, picks):
    new_ids = [p.id for p in picks if p.id not in (visit.current or [])]
    visit.current = [p.id for p in picks]
    visit.seen = list(dict.fromkeys((visit.seen or []) + new_ids))
    log_events(db, visit, "shown", new_ids)


def exclusions(visit, items, extra=()):
    """Avoid repeats; once everything has been seen, only keep hard rejections out."""
    excl = set(visit.rejected or []) | set(visit.seen or []) | set(extra)
    available = [i for i in items if i.available and i.embedding and i.id not in excl]
    if len(available) < recommend.SET_SIZE:
        visit.seen = []
        excl = set(visit.rejected or []) | set(extra)
    return excl


def state(db, visit):
    items = all_items(db)
    by_id = {i.id: i for i in items}
    pop = popular_ids(db)
    picks = [card(by_id[i], visit, items, pop) for i in visit.current or [] if i in by_id]
    return {"table": visit.table_no, "mood": visit.mood, "picks": picks, "cafe": cafe_name(db)}


# ---------- pages ----------

def public_base(request: Request) -> str:
    """Address used inside QR codes. PUBLIC_URL wins, because phones can't open localhost."""
    return (os.getenv("PUBLIC_URL") or str(request.base_url)).rstrip("/")


def table_link(request: Request, t: CafeTable) -> str:
    return f"{public_base(request)}/t/{t.number}?k={t.token}"


def new_token() -> str:
    return secrets.token_urlsafe(6)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db=Depends(get_db)):
    demo = db.scalar(select(CafeTable).where(CafeTable.active.is_(True)).order_by(CafeTable.number))
    return templates.TemplateResponse(request, "home.html", {
        "cafe": cafe_name(db),
        "demo_link": f"/t/{demo.number}?k={demo.token}" if demo else None,
        "demo_label": demo.label if demo else None,
    })


@app.get("/t/{table_no}", response_class=HTMLResponse)
def table_page(table_no: int, request: Request, k: str = "", db=Depends(get_db)):
    table = db.scalar(select(CafeTable).where(CafeTable.number == table_no))
    if not table or not hmac.compare_digest(k, table.token):
        return templates.TemplateResponse(request, "table_closed.html", {
            "cafe": cafe_name(db), "title": "Scan the QR on your table",
            "message": "This link has expired or isn't complete. Scan the code on your table to order.",
        }, status_code=404)
    if not table.active:
        return templates.TemplateResponse(request, "table_closed.html", {
            "cafe": cafe_name(db), "title": f"{table.label} is resting",
            "message": "This table isn't taking orders right now. Please order at the counter.",
        })
    vid = request.cookies.get("visit")
    visit = db.get(Visit, vid) if vid else None
    fresh = not visit or visit.table_no != table_no or (utcnow() - visit.last_seen) > timedelta(hours=3)
    if fresh:
        visit = Visit(id=str(uuid.uuid4()), table_no=table_no)
        db.add(visit)
        db.commit()
    resp = templates.TemplateResponse(request, "table.html", {"cafe": cafe_name(db), "table": table_no, "table_label": table.label})
    resp.set_cookie("visit", visit.id, max_age=6 * 3600, httponly=True, samesite="lax")
    return resp


@app.get("/qr/site.svg")
def qr_site(request: Request):
    """QR for the app's own home page (shown on the /admin page)."""
    buf = io.BytesIO()
    segno.make(public_base(request), error="h").save(buf, kind="svg", scale=8, border=2, dark="#2b1d14")
    return Response(buf.getvalue(), media_type="image/svg+xml")


# ---------- customer API ----------

class MoodIn(BaseModel):
    mood: str


class ReactIn(BaseModel):
    item_id: int
    reaction: str


class SetIn(BaseModel):
    action: str


class OrderLine(BaseModel):
    id: int
    qty: int = 1


class OrderIn(BaseModel):
    items: list[OrderLine]
    note: str = ""


@app.get("/api/visit")
def get_visit(request: Request, db=Depends(get_db)):
    visit = current_visit(request, db)
    db.commit()
    return state(db, visit)


@app.post("/api/mood")
def choose_mood(body: MoodIn, request: Request, db=Depends(get_db)):
    if body.mood not in recommend.MOODS:
        raise HTTPException(400, "Unknown mood")
    visit = current_visit(request, db)
    items = all_items(db)
    visit.mood = body.mood
    visit.pref = recommend.initial_pref(items, body.mood)
    visit.reactions, visit.liked, visit.rejected, visit.seen, visit.current = {}, [], [], [], []
    set_picks(db, visit, items, recommend.pick(items, visit))
    db.add(Event(visit_id=visit.id, kind=f"mood_{body.mood}"))
    db.commit()
    return state(db, visit)


@app.post("/api/react")
def react(body: ReactIn, request: Request, db=Depends(get_db)):
    if body.reaction not in recommend.WEIGHTS:
        raise HTTPException(400, "Unknown reaction")
    visit = current_visit(request, db)
    items = all_items(db)
    item = next((i for i in items if i.id == body.item_id), None)
    if not item or not visit.mood:
        raise HTTPException(400, "Pick a mood first")

    visit.pref = recommend.nudge(visit.pref, item, recommend.WEIGHTS[body.reaction], items)
    visit.reactions = {**(visit.reactions or {}), str(item.id): body.reaction}
    db.add(Event(visit_id=visit.id, item_id=item.id, kind=body.reaction))

    if body.reaction == "like":
        visit.liked = list(dict.fromkeys((visit.liked or []) + [item.id]))
    elif body.reaction == "nope":
        visit.rejected = list(dict.fromkeys((visit.rejected or []) + [item.id]))
        current = list(visit.current or [])
        if item.id in current:
            # Swap just that card for the best new match, in the same position.
            by_id = {i.id: i for i in items}
            pos = current.index(item.id)
            keep = [i for i in current if i != item.id]
            picks = recommend.pick(items, visit, keep_ids=keep, exclude_ids=exclusions(visit, items))
            new = [p.id for p in picks if p.id not in keep][:1]
            set_picks(db, visit, items, [by_id[i] for i in keep[:pos] + new + keep[pos:]])
    db.commit()
    return state(db, visit)


@app.post("/api/set")
def set_action(body: SetIn, request: Request, db=Depends(get_db)):
    visit = current_visit(request, db)
    items = all_items(db)
    by_id = {i.id: i for i in items}
    if not visit.mood:
        raise HTTPException(400, "Pick a mood first")
    current = [by_id[i] for i in visit.current or [] if i in by_id]
    reactions = visit.reactions or {}
    db.add(Event(visit_id=visit.id, kind=f"set_{body.action}"))

    if body.action == "love":
        # Everything on screen that wasn't explicitly judged counts as a soft like.
        for it in current:
            if str(it.id) not in reactions:
                visit.pref = recommend.nudge(visit.pref, it, 0.5, items)
                visit.liked = list(dict.fromkeys((visit.liked or []) + [it.id]))
        db.commit()
        return {**state(db, visit), "view": "ranked"}

    if body.action == "mixed":
        liked = [it for it in current if reactions.get(str(it.id)) == "like"]
        if not liked:  # nothing marked: keep the two best matches
            sc = recommend.scores(current, visit, items)
            liked = sorted(current, key=lambda i: -sc.get(i.id, 0))[:2]
        keep = [it.id for it in liked]
        for it in current:
            visit.pref = recommend.nudge(visit.pref, it, 0.3 if it.id in keep else -0.3, items)
        swapped = [it.id for it in current if it.id not in keep]
        picks = recommend.pick(items, visit, keep_ids=keep, exclude_ids=exclusions(visit, items, swapped))
    elif body.action == "nope":
        for it in current:
            visit.pref = recommend.nudge(visit.pref, it, -0.5, items)
        visit.rejected = list(dict.fromkeys((visit.rejected or []) + [it.id for it in current]))
        picks = recommend.pick(items, visit, exclude_ids=exclusions(visit, items))
    else:
        raise HTTPException(400, "Unknown action")

    visit.reactions = {k: v for k, v in reactions.items() if int(k) in {p.id for p in picks}}
    set_picks(db, visit, items, picks)
    db.commit()
    return {**state(db, visit), "view": "picks"}


@app.get("/api/menu")
def menu(request: Request, ranked: bool = False, db=Depends(get_db)):
    visit = current_visit(request, db)
    items = all_items(db)
    pop = popular_ids(db)
    sc = recommend.scores(items, visit, items) if (ranked and visit.mood) else {}
    if ranked and sc:
        rejected = set(visit.rejected or [])
        ordered = sorted(items, key=lambda i: (not i.available, i.id in rejected, -sc.get(i.id, -1)))
    else:
        ordered = items
    db.commit()
    return {"ranked": bool(sc), "items": [card(i, visit, items, pop, sc.get(i.id)) for i in ordered]}


@app.post("/api/order")
def place_order(body: OrderIn, request: Request, db=Depends(get_db)):
    visit = current_visit(request, db)
    table = db.scalar(select(CafeTable).where(CafeTable.number == visit.table_no))
    if not table or not table.active:
        raise HTTPException(409, "This table isn't taking orders right now. Please order at the counter.")
    by_id = {i.id: i for i in all_items(db)}
    lines = [
        {"id": l.id, "name": by_id[l.id].name, "qty": max(1, min(l.qty, 20)), "price": by_id[l.id].price}
        for l in body.items if l.id in by_id and by_id[l.id].available
    ]
    if not lines:
        raise HTTPException(400, "Your cart is empty")
    order = Order(visit_id=visit.id, table_no=visit.table_no, items=lines, note=body.note.strip()[:300])
    db.add(order)
    log_events(db, visit, "order", [l["id"] for l in lines])
    db.commit()
    return order_status(order.id, request, db)


@app.get("/api/order/{order_id}")
def order_status(order_id: int, request: Request, db=Depends(get_db)):
    visit = current_visit(request, db)
    order = db.get(Order, order_id)
    if not order or order.visit_id != visit.id:
        raise HTTPException(404)
    ahead = db.scalar(select(func.count(Order.id)).where(Order.status == "new", Order.id < order.id))
    db.commit()
    return {"id": order.id, "status": order.status, "ahead": ahead, "items": order.items}


# ---------- owner / staff ----------

# Accounts: email + scrypt-hashed password. Registering needs the staff invite code (ADMIN_PIN),
# so a stranger who finds /admin on the public site can't create an account.

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
        return hmac.compare_digest(test.hex(), digest)
    except ValueError:
        return False


def admin_token(admin: Admin) -> str:
    # Tied to the password hash, so changing a password logs out old sessions.
    sig = hmac.new(SECRET.encode(), f"admin:{admin.id}:{admin.password_hash}".encode(), hashlib.sha256).hexdigest()
    return f"{admin.id}.{sig}"


def current_admin(request: Request, db) -> Admin | None:
    admin_id, _, _ = request.cookies.get("admin", "").partition(".")
    admin = db.get(Admin, int(admin_id)) if admin_id.isdigit() else None
    if admin and hmac.compare_digest(request.cookies.get("admin", ""), admin_token(admin)):
        return admin
    return None


def require_admin(request: Request, db=Depends(get_db)):
    if not current_admin(request, db):
        raise HTTPException(401, "Owner login required")


def auth_page(request, db, mode="login", error="", email="", name="", status=200):
    return templates.TemplateResponse(
        request, "login.html",
        {"cafe": cafe_name(db), "mode": mode, "error": error, "email": email, "name": name},
        status_code=status,
    )


def logged_in(admin: Admin):
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie("admin", admin_token(admin), max_age=12 * 3600, httponly=True, samesite="lax",
                    secure=os.getenv("K_SERVICE") is not None)  # K_SERVICE is set on Cloud Run (https)
    return resp


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, mode: str = "login", db=Depends(get_db)):
    admin = current_admin(request, db)
    if not admin:
        return auth_page(request, db, mode="register" if mode == "register" else "login")
    return templates.TemplateResponse(request, "admin.html", {"cafe": cafe_name(db), "admin_name": admin.name})


@app.post("/admin/login")
def admin_login(request: Request, email: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    email = email.strip().lower()
    admin = db.scalar(select(Admin).where(Admin.email == email))
    if not admin or not check_password(password, admin.password_hash):
        return auth_page(request, db, error="That email and password don't match.", email=email, status=401)
    return logged_in(admin)


@app.post("/admin/register")
def admin_register(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...),
                   invite: str = Form(...), db=Depends(get_db)):
    name, email = name.strip()[:80], email.strip().lower()[:160]

    def fail(msg):
        return auth_page(request, db, mode="register", error=msg, email=email, name=name, status=400)

    if not hmac.compare_digest(invite.strip(), ADMIN_PIN):
        return fail("That staff invite code isn't right. Ask the café owner for it.")
    if not name or "@" not in email or "." not in email.split("@")[-1]:
        return fail("Please enter your name and a valid email.")
    if len(password) < 8:
        return fail("Use a password with at least 8 characters.")
    if db.scalar(select(Admin).where(Admin.email == email)):
        return fail("An account with that email already exists. Log in instead.")
    admin = Admin(name=name, email=email, password_hash=hash_password(password))
    db.add(admin)
    db.commit()
    return logged_in(admin)


@app.post("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/admin", status_code=303)
    resp.delete_cookie("admin")
    return resp


# ---------- tables (owner) ----------

ZONES = ["Indoor", "Window", "Outdoor", "Counter", "Private"]


def table_json(request, t: CafeTable, live: set[int], open_orders: Counter):
    return {
        "id": t.id, "number": t.number, "name": t.name, "label": t.label, "seats": t.seats, "zone": t.zone,
        "active": t.active, "link": table_link(request, t), "live": t.number in live,
        "open_orders": open_orders.get(t.number, 0),
    }


@app.get("/api/admin/tables", dependencies=[Depends(require_admin)])
def list_tables(request: Request, db=Depends(get_db)):
    tables = db.scalars(select(CafeTable).order_by(CafeTable.number)).all()
    live = set(db.scalars(select(Visit.table_no).where(Visit.last_seen >= utcnow() - timedelta(minutes=30))).all())
    open_orders = Counter(db.scalars(select(Order.table_no).where(Order.status != "served")).all())
    return {"zones": ZONES, "tables": [table_json(request, t, live, open_orders) for t in tables]}


class TablesAddIn(BaseModel):
    count: int = 1
    seats: int = 2
    zone: str = "Indoor"


@app.post("/api/admin/tables", dependencies=[Depends(require_admin)])
def add_tables(body: TablesAddIn, db=Depends(get_db)):
    count = max(1, min(body.count, 50))
    total = db.scalar(select(func.count(CafeTable.id))) or 0
    if total + count > 200:
        raise HTTPException(400, "That would be more than 200 tables.")
    start = (db.scalar(select(func.max(CafeTable.number))) or 0) + 1
    for n in range(start, start + count):
        db.add(CafeTable(number=n, seats=max(1, min(body.seats, 30)), zone=body.zone[:40] or "Indoor", token=new_token()))
    db.commit()
    return {"ok": True, "added": list(range(start, start + count))}


class TablePatch(BaseModel):
    name: str | None = None
    seats: int | None = None
    zone: str | None = None
    active: bool | None = None


@app.patch("/api/admin/tables/{table_id}", dependencies=[Depends(require_admin)])
def edit_table(table_id: int, body: TablePatch, db=Depends(get_db)):
    t = db.get(CafeTable, table_id)
    if not t:
        raise HTTPException(404)
    if body.name is not None:
        t.name = body.name.strip()[:60]
    if body.seats is not None:
        t.seats = max(1, min(body.seats, 30))
    if body.zone is not None:
        t.zone = body.zone.strip()[:40] or "Indoor"
    if body.active is not None:
        t.active = body.active
    db.commit()
    return {"ok": True}


@app.post("/api/admin/tables/{table_id}/new-qr", dependencies=[Depends(require_admin)])
def regenerate_qr(table_id: int, db=Depends(get_db)):
    t = db.get(CafeTable, table_id)
    if not t:
        raise HTTPException(404)
    t.token = new_token()
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/tables/{table_id}", dependencies=[Depends(require_admin)])
def delete_table(table_id: int, db=Depends(get_db)):
    t = db.get(CafeTable, table_id)
    if t:
        db.delete(t)
        db.commit()
    return {"ok": True}


# Table QRs contain the table's secret code, so only logged-in owners can fetch them.
@app.get("/qr/table/{number}.{fmt}", dependencies=[Depends(require_admin)])
def table_qr(number: int, fmt: str, request: Request, db=Depends(get_db)):
    t = db.scalar(select(CafeTable).where(CafeTable.number == number))
    if not t or fmt not in ("svg", "png"):
        raise HTTPException(404)
    qr = segno.make(table_link(request, t), error="m")
    buf = io.BytesIO()
    if fmt == "svg":
        qr.save(buf, kind="svg", scale=8, border=2, dark="#2b1d14")
        return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
    qr.save(buf, kind="png", scale=16, border=3, dark="#2b1d14")
    filename = f"{t.label.replace(' ', '-').lower()}-qr.png"
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def collect_stats(db, hours=24):
    since = utcnow() - timedelta(hours=hours)
    items = all_items(db)
    per = defaultdict(Counter)
    for item_id, kind, n in db.execute(
        select(Event.item_id, Event.kind, func.count())
        .where(Event.created_at >= since, Event.item_id.isnot(None))
        .group_by(Event.item_id, Event.kind)
    ):
        per[item_id][kind] = n
    other = Counter({k: n for k, n in db.execute(
        select(Event.kind, func.count()).where(Event.created_at >= since, Event.item_id.is_(None)).group_by(Event.kind)
    )})
    rows = []
    for i in items:
        c = per.get(i.id, Counter())
        reacted = c["like"] + c["meh"] + c["nope"]
        rows.append({
            "id": i.id, "name": i.name, "category": i.category, "price": i.price, "available": i.available,
            "shown": c["shown"], "like": c["like"], "meh": c["meh"], "nope": c["nope"], "ordered": c["order"],
            "love_rate": round(c["like"] / reacted, 2) if reacted else None,
        })
    rows.sort(key=lambda r: -(r["shown"] + r["like"] + r["nope"] + r["ordered"]))
    active = db.scalar(select(func.count(func.distinct(Visit.table_no))).where(Visit.last_seen >= utcnow() - timedelta(minutes=30)))
    moods = {m: other.get(f"mood_{m}", 0) for m in recommend.MOODS}
    sets = {a: other.get(f"set_{a}", 0) for a in ("love", "mixed", "nope")}

    def top(key, min_n=1):
        best = max(rows, key=lambda r: r[key], default=None)
        return best if best and best[key] >= min_n else None

    liked_not_ordered = [r["name"] for r in rows if r["like"] >= 2 and r["ordered"] == 0]
    return {
        "items": rows, "moods": moods, "set_buttons": sets, "active_tables": active or 0,
        "taps": sum(r["like"] + r["meh"] + r["nope"] for r in rows) + sum(sets.values()),
        "highlights": {
            "top_loved": top("like"), "most_rejected": top("nope"), "most_ordered": top("ordered"),
            "liked_not_ordered": liked_not_ordered[:3],
        },
    }


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats(db=Depends(get_db)):
    stats = collect_stats(db)
    orders = db.scalars(select(Order).where(Order.status != "served").order_by(Order.id)).all()
    labels = {t.number: t.label for t in db.scalars(select(CafeTable)).all()}
    stats["orders"] = [
        {"id": o.id, "table": o.table_no, "table_label": labels.get(o.table_no, f"Table {o.table_no}"), "items": o.items, "note": o.note, "status": o.status,
         "age_min": int((utcnow() - o.created_at).total_seconds() // 60)}
        for o in orders
    ]
    return stats


@app.post("/api/admin/insights", dependencies=[Depends(require_admin)])
def admin_insights(db=Depends(get_db)):
    stats = collect_stats(db)
    if stats["taps"] < 5:
        return {"insights": [], "message": "Need a few more taps from tables before Gemini can spot patterns."}
    compact = {
        "items": [{k: r[k] for k in ("name", "category", "price", "shown", "like", "meh", "nope", "ordered")}
                  for r in stats["items"] if r["shown"] or r["like"] or r["nope"] or r["ordered"]],
        "moods_chosen": stats["moods"], "set_buttons": stats["set_buttons"],
    }
    try:
        return {"insights": ai.owner_insights(cafe_name(db), compact)}
    except Exception as e:
        log.exception("insights failed")
        raise HTTPException(502, f"Gemini error: {e}")


class StatusIn(BaseModel):
    status: str


@app.post("/api/admin/orders/{order_id}", dependencies=[Depends(require_admin)])
def update_order(order_id: int, body: StatusIn, db=Depends(get_db)):
    order = db.get(Order, order_id)
    if not order or body.status not in ("new", "ready", "served"):
        raise HTTPException(400)
    order.status = body.status
    db.commit()
    return {"ok": True}


@app.get("/api/admin/menu", dependencies=[Depends(require_admin)])
def admin_menu(db=Depends(get_db)):
    return {"cafe": cafe_name(db), "items": [
        {"id": i.id, "name": i.name, "category": i.category, "price": i.price, "veg": i.veg,
         "allergens": i.allergens, "available": i.available, "blurb": i.blurb}
        for i in all_items(db)
    ]}


@app.post("/api/admin/menu/extract", dependencies=[Depends(require_admin)])
async def extract(photo: UploadFile = File(...)):
    data = await photo.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Photo too large (max 15 MB)")
    mime = photo.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise HTTPException(400, "Please upload an image")
    try:
        return {"items": ai.extract_menu(data, mime)}
    except Exception as e:
        log.exception("extract failed")
        raise HTTPException(502, f"Gemini couldn't read that photo: {e}")


class DraftIn(BaseModel):
    name: str
    description: str = ""
    price: float | None = None
    category: str = "Other"
    veg: bool = True
    allergens: list[str] = []
    tags: list[str] = []
    blurb: str = ""


class SaveMenuIn(BaseModel):
    items: list[DraftIn]
    replace: bool = False
    cafe_name: str | None = None


@app.post("/api/admin/menu/save", dependencies=[Depends(require_admin)])
def save_menu(body: SaveMenuIn, db=Depends(get_db)):
    drafts = [d.model_dump() for d in body.items if d.name.strip()]
    if not drafts:
        raise HTTPException(400, "No items to save")
    if body.cafe_name and body.cafe_name.strip():
        set_setting(db, "cafe_name", body.cafe_name.strip()[:80])
    if body.replace:
        remove_items(db, all_items(db))
    try:
        add_items(db, drafts)
    except Exception as e:
        log.exception("save failed")
        raise HTTPException(502, f"Saved items, but embedding failed: {e}")
    return {"ok": True, "count": len(drafts)}


@app.post("/api/admin/menu/demo", dependencies=[Depends(require_admin)])
def load_demo(db=Depends(get_db)):
    remove_items(db, all_items(db))
    set_setting(db, "cafe_name", DEFAULT_CAFE_NAME)
    add_items(db, demo_items())
    return {"ok": True}


class ItemPatch(BaseModel):
    available: bool | None = None
    price: float | None = None


@app.patch("/api/admin/menu/{item_id}", dependencies=[Depends(require_admin)])
def patch_item(item_id: int, body: ItemPatch, db=Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(404)
    if body.available is not None:
        item.available = body.available
    if body.price is not None:
        item.price = body.price
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/menu/{item_id}", dependencies=[Depends(require_admin)])
def delete_item(item_id: int, db=Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if item:
        remove_items(db, [item])
        db.commit()
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return JSONResponse({"ok": True})
