"""Quick check that the app can reach its database: python check_db.py"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402

with engine.connect() as c:
    print("Connected to:", engine.url.render_as_string(hide_password=True))
    print(c.execute(text("select version()")).scalar() if engine.dialect.name == "postgresql" else "SQLite")
