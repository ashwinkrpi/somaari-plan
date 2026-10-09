"""SQLite helpers: connect (WAL, foreign keys) and migrate from schema.sql."""
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT

IST = ZoneInfo("Asia/Kolkata")
SCHEMA = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_DB = ROOT / "data" / "somaari.db"


def now_iso():
    return datetime.now(IST).isoformat(timespec="seconds")


def connect(path=None):
    path = Path(path or DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn):
    conn.executescript(SCHEMA.read_text())
    conn.commit()


def init_db(path=None):
    conn = connect(path)
    migrate(conn)
    conn.close()
