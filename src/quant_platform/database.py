"""SQLite database connection and migration management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    if db_path is None:
        settings = get_settings()
        db_path = settings.db_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def run_migrations(conn: sqlite3.Connection) -> int:
    applied = 0
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        sql = sql_file.read_text()
        conn.executescript(sql)
        applied += 1
    return applied
