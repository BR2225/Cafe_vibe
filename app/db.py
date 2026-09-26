"""Database models. SQLite locally, Cloud SQL (PostgreSQL) on Cloud Run."""
import os
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _database_url():
    # On Cloud Run, Cloud SQL is mounted as a Unix socket under /cloudsql/<connection name>.
    conn = os.getenv("INSTANCE_CONNECTION_NAME")
    if conn:
        return URL.create(
            "postgresql+psycopg",
            username=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            database=os.getenv("DB_NAME", "cafe"),
            query={"host": f"/cloudsql/{conn}"},
        )
    # Local dev against Cloud SQL's public IP (your IP must be in Authorized networks).
    host = os.getenv("DB_HOST")
    if host:
        return URL.create(
            "postgresql+psycopg",
            username=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            host=host,
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "cafe"),
            query={"sslmode": "require", "connect_timeout": "10"},
        )
    return make_url(os.getenv("DATABASE_URL", "sqlite:///./cafe.db"))


def _connector_engine():
    """Local dev via the Cloud SQL Python Connector (port 3307, Google credentials, no IP allow-list)."""
    from google.cloud.sql.connector import Connector, IPTypes

    connector = Connector(ip_type=IPTypes.PUBLIC)

    def getconn():
        return connector.connect(
            os.environ["INSTANCE_CONNECTION_NAME"], "pg8000",
            user=os.environ["DB_USER"], password=os.environ["DB_PASS"], db=os.getenv("DB_NAME", "cafe"),
        )

    return create_engine("postgresql+pg8000://", creator=getconn, pool_pre_ping=True, pool_size=5, max_overflow=2)


if os.getenv("USE_SQL_CONNECTOR") == "1":
    engine = _connector_engine()
else:
    _url = _database_url()
    if _url.get_backend_name() == "sqlite":
        engine = create_engine(_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(_url, pool_pre_ping=True, pool_size=5, max_overflow=2)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = {"sqlite_autoincrement": True}  # never reuse ids, so old taps can't attach to new items
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str] = mapped_column(String(60), default="Other")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    allergens: Mapped[list] = mapped_column(JSON, default=list)
    veg: Mapped[bool] = mapped_column(Boolean, default=True)
    blurb: Mapped[str] = mapped_column(Text, default="")
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Visit(Base):
    """One customer session at a table (anonymous, cookie-based)."""
    __tablename__ = "visits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    table_no: Mapped[int] = mapped_column(Integer)
    mood: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pref: Mapped[list | None] = mapped_column(JSON, nullable=True)  # taste vector
    current: Mapped[list] = mapped_column(JSON, default=list)  # item ids in the suggested set
    reactions: Mapped[dict] = mapped_column(JSON, default=dict)  # {item_id: like|meh|nope}
    liked: Mapped[list] = mapped_column(JSON, default=list)
    rejected: Mapped[list] = mapped_column(JSON, default=list)
    seen: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Event(Base):
    """Every tap: shown / like / meh / nope / set_love / set_mixed / set_nope / order."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[str] = mapped_column(String(36), index=True)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[str] = mapped_column(String(36), index=True)
    table_no: Mapped[int] = mapped_column(Integer)
    items: Mapped[list] = mapped_column(JSON)  # [{id, name, qty, price}]
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | ready | served
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


def init_db():
    Base.metadata.create_all(engine)


def get_setting(db, key, default=""):
    row = db.get(Setting, key)
    return row.value if row else default


def set_setting(db, key, value):
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
