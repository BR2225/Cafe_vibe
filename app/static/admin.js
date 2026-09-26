// Owner dashboard: live stats + orders (polled), Gemini insights, photo -> menu, table QR codes.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const CUR = document.body.dataset.currency || "₹";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (p) => (p == null ? "–" : `${CUR}${Number(p).toLocaleString("en-IN")}`);

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2600);
}

async function api(path, { method = "GET", body, form } = {}) {
  const r = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: form || (body ? JSON.stringify(body) : undefined),
  });
  if (r.status === 401) { location.reload(); throw new Error("Logged out"); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

// ---------- tabs ----------
$$(".tabs button").forEach((b) =>
  b.addEventListener("click", () => {
    $$(".tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    $$("main > section").forEach((s) => (s.hidden = s.id !== `tab-${b.dataset.tab}`));
    if (b.dataset.tab === "menu") loadMenu();
    if (b.dataset.tab === "tables") renderQRs();
  })
);

// ---------- live ----------
async function refresh() {
  let s;
  try { s = await api("/api/admin/stats"); } catch { return; }
  $("#kTables").textContent = s.active_tables;
  $("#kTaps").textContent = s.taps;
  $("#kMoods").innerHTML = `${Icon.work("icon-sm")} ${s.moods.work} · ${Icon.meet("icon-sm")} ${s.moods.meet} · ${Icon.unwind("icon-sm")} ${s.moods.unwind}`;
  $("#kSets").innerHTML = `${Icon.heart("icon-sm")} ${s.set_buttons.love} · ${Icon.meh("icon-sm")} ${s.set_buttons.mixed} · ${Icon.nope("icon-sm")} ${s.set_buttons.nope}`;

  const h = s.highlights;
  $("#highlights").innerHTML = `
    <div class="hl good"><small>Most loved</small><b>${h.top_loved ? `${esc(h.top_loved.name)} · ${Icon.heart("icon-sm")} ${h.top_loved.like}` : "No likes yet"}</b></div>
    <div class="hl bad"><small>Most rejected</small><b>${h.most_rejected ? `${esc(h.most_rejected.name)} · ${Icon.nope("icon-sm")} ${h.most_rejected.nope}` : "Nothing rejected yet"}</b></div>
    <div class="hl"><small>Loved but not ordered</small><b>${h.liked_not_ordered.length ? esc(h.liked_not_ordered.join(", ")) : "–"}</b></div>`;

  const active = s.items.filter((r) => r.shown || r.like || r.meh || r.nope || r.ordered);
  $("#statRows").innerHTML = active.length
    ? active.map((r) => `<tr>
        <td>${esc(r.name)} <small class="muted">${esc(r.category)}</small></td>
        <td>${r.shown}</td><td>${r.like}</td><td>${r.meh}</td><td>${r.nope}</td><td>${r.ordered}</td>
        <td>${r.love_rate == null ? "–" : `${Math.round(r.love_rate * 100)}%<span class="bar"><i style="width:${r.love_rate * 100}%"></i></span>`}</td>
      </tr>`).join("")
    : `<tr><td colspan="7" class="muted">No taps yet. Open a table page (Table QRs tab) and start tapping.</td></tr>`;

  const open = s.orders;
  $("#orderCount").textContent = open.length ? `${open.length} open` : "";
  $("#orders").innerHTML = open.length
    ? open.map((o) => `<div class="order ${o.status}">
        <div class="order-head"><span>Table ${o.table}</span><span class="muted">#${o.id} · ${o.age_min}m</span></div>
        <div>${o.items.map((l) => `${l.qty}× ${esc(l.name)}`).join(", ")}</div>
        ${o.note ? `<div class="muted">“${esc(o.note)}”</div>` : ""}
        <div class="row-actions">
          ${o.status === "new" ? `<button class="btn primary" data-order="${o.id}" data-status="ready">Mark ready</button>` : ""}
          <button class="btn ghost" data-order="${o.id}" data-status="served">Served</button>
        </div></div>`).join("")
    : '<p class="muted">No open orders.</p>';
}

$("#orders").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-order]");
  if (!b) return;
  b.disabled = true;
  try {
    await api(`/api/admin/orders/${b.dataset.order}`, { method: "POST", body: { status: b.dataset.status } });
    refresh();
  } catch (err) { toast(err.message); b.disabled = false; }
});

$("#askGemini").addEventListener("click", async () => {
  const b = $("#askGemini");
  b.disabled = true;
  b.innerHTML = '<span class="spinner"></span> Thinking…';
  try {
    const r = await api("/api/admin/insights", { method: "POST" });
    $("#insightHint").textContent = r.message || "Based on the last 24 hours of taps:";
    $("#insights").innerHTML = (r.insights || []).map((i) => `
      <div class="insight"><b>${esc(i.headline)}</b><p>${esc(i.detail)}</p><div class="action">${Icon.arrowLeft("icon-sm rotate")} ${esc(i.action)}</div></div>`).join("");
  } catch (err) { toast(err.message); }
  b.disabled = false;
  b.textContent = "Ask again";
});

$("#insightHead").innerHTML = `${Icon.spark("icon-sm")} What should I change?`;
$("#photoHead").innerHTML = `${Icon.camera()} Photograph your menu`;
$("#draftWarn").innerHTML = `${Icon.warning("icon-sm")} Gemini guessed the allergens. Check each item before publishing.`;
$("#thLove").innerHTML = Icon.heart("icon-sm");
$("#thMeh").innerHTML = Icon.meh("icon-sm");
$("#thNope").innerHTML = Icon.nope("icon-sm");

refresh();
setInterval(() => { if (!$("#tab-live").hidden && !document.hidden) refresh(); }, 4000);

// ---------- menu ----------
async function loadMenu() {
  const m = await api("/api/admin/menu");
  $("#cafeName").textContent = m.cafe;
  $("#menuRows").innerHTML = m.items.map((i) => `
    <div class="menu-row">
      <div><b>${esc(i.name)}</b> <span class="muted">${esc(i.category)}${i.allergens?.length ? " · " + esc(i.allergens.join(", ")) : ""}</span></div>
      <span>${money(i.price)}</span>
      <button class="toggle ${i.available ? "" : "off"}" data-avail="${i.id}" data-on="${i.available}">${i.available ? "Available" : "Sold out"}</button>
      <button class="link" data-del="${i.id}" aria-label="Delete ${esc(i.name)}">Delete</button>
    </div>`).join("") || '<p class="muted">No items yet.</p>';
}

$("#menuRows").addEventListener("click", async (e) => {
  const a = e.target.closest("[data-avail]");
  const d = e.target.closest("[data-del]");
  try {
    if (a) await api(`/api/admin/menu/${a.dataset.avail}`, { method: "PATCH", body: { available: a.dataset.on !== "true" } });
    if (d && confirm("Delete this item?")) await api(`/api/admin/menu/${d.dataset.del}`, { method: "DELETE" });
    if (a || d) loadMenu();
  } catch (err) { toast(err.message); }
});

$("#resetDemo").addEventListener("click", async () => {
  if (!confirm("Replace the whole menu with the demo menu?")) return;
  try { await api("/api/admin/menu/demo", { method: "POST" }); toast("Demo menu loaded"); loadMenu(); } catch (err) { toast(err.message); }
});

$("#photo").addEventListener("change", () => {
  const f = $("#photo").files[0];
  $("#photoLabel").textContent = f ? f.name.slice(0, 24) : "Choose photo";
  $("#extractBtn").disabled = !f;
});

$("#extractBtn").addEventListener("click", async () => {
  const f = $("#photo").files[0];
  if (!f) return;
  const b = $("#extractBtn");
  b.disabled = true;
  b.innerHTML = '<span class="spinner"></span> Gemini is reading your menu…';
  const form = new FormData();
  form.append("photo", f);
  try {
    const r = await api("/api/admin/menu/extract", { method: "POST", form });
    if (!r.items.length) throw new Error("Couldn't find menu items in that photo. Try a sharper, straight-on shot.");
    renderDraft(r.items);
    toast(`Found ${r.items.length} items. Check them below.`);
  } catch (err) { toast(err.message); }
  b.disabled = false;
  b.textContent = "Read menu with Gemini";
});

let draft = [];
function renderDraft(items) {
  draft = items;
  $("#draftWrap").hidden = false;
  $("#draftRows").innerHTML = items.map((i, n) => `
    <tr data-n="${n}">
      <td><input data-f="name" value="${esc(i.name)}"></td>
      <td><input data-f="category" value="${esc(i.category)}"></td>
      <td><input data-f="price" type="number" step="any" value="${i.price ?? ""}" style="width:90px"></td>
      <td><input data-f="veg" type="checkbox" ${i.veg ? "checked" : ""} style="width:auto"></td>
      <td><input data-f="allergens" value="${esc((i.allergens || []).join(", "))}"></td>
      <td><input data-f="blurb" value="${esc(i.blurb)}"></td>
      <td><button class="link" data-drop="${n}" aria-label="Remove">${Icon.nope("icon-sm")}</button></td>
    </tr>`).join("");
}

$("#draftRows").addEventListener("click", (e) => {
  const d = e.target.closest("[data-drop]");
  if (d) d.closest("tr").remove();
});

function collectDraft() {
  return $$("#draftRows tr").map((tr) => {
    const base = draft[Number(tr.dataset.n)];
    const v = (f) => $(`[data-f=${f}]`, tr);
    return {
      ...base,
      name: v("name").value.trim(),
      category: v("category").value.trim() || "Other",
      price: v("price").value === "" ? null : Number(v("price").value),
      veg: v("veg").checked,
      allergens: v("allergens").value.split(",").map((a) => a.trim()).filter(Boolean),
      blurb: v("blurb").value.trim(),
    };
  }).filter((i) => i.name);
}

async function publish(replace) {
  const items = collectDraft();
  if (!items.length) return toast("Nothing to publish");
  const btns = [$("#publishReplace"), $("#publishAdd")];
  btns.forEach((b) => (b.disabled = true));
  try {
    await api("/api/admin/menu/save", { method: "POST", body: { items, replace, cafe_name: $("#newCafeName").value || null } });
    toast(`Published ${items.length} items. Your QR menu is live.`);
    $("#draftWrap").hidden = true;
    loadMenu();
  } catch (err) { toast(err.message); }
  btns.forEach((b) => (b.disabled = false));
}
$("#publishReplace").addEventListener("click", () => confirm("Replace the entire current menu?") && publish(true));
$("#publishAdd").addEventListener("click", () => publish(false));
$("#discardDraft").addEventListener("click", () => { $("#draftWrap").hidden = true; draft = []; });

// ---------- table QRs ----------
function renderQRs() {
  const n = Math.max(1, Math.min(60, Number($("#tableCount").value) || 1));
  const cafe = esc($("#cafeName").textContent);
  $("#qrGrid").innerHTML = Array.from({ length: n }, (_, i) => i + 1).map((t) => `
    <div class="qr-card"><img src="/qr/${t}.svg" alt="QR code for table ${t}" loading="lazy">
      <b>Table ${t}</b><small>${cafe} · Scan to order</small><br><a href="/t/${t}" target="_blank" rel="noopener">Open</a></div>`).join("");
}
$("#tableCount").addEventListener("change", renderQRs);
$("#printQr").addEventListener("click", () => window.print());
