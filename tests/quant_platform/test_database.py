"""Unit tests for database connection and migrations."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from quant_platform.database import get_connection, run_migrations


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()
    Path(db_path).unlink(missing_ok=True)


def test_connection_wal_mode(tmp_db):
    conn, _ = tmp_db
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_connection_foreign_keys_on(tmp_db):
    conn, _ = tmp_db
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_migrations_create_tables(tmp_db):
    conn, _ = tmp_db
    applied = run_migrations(conn)
    assert applied >= 1
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    assert "assets" in tables
    assert "portfolios" in tables
    assert "positions" in tables
    assert "trades" in tables
    assert "schema_versions" in tables


def test_migrations_idempotent(tmp_db):
    conn, _ = tmp_db
    run_migrations(conn)
    run_migrations(conn)
    count = conn.execute("SELECT COUNT(*) FROM schema_versions").fetchone()[0]
    assert count == 1


def test_trade_simulation_constraint(tmp_db):
    conn, _ = tmp_db
    run_migrations(conn)
    conn.execute(
        "INSERT INTO assets (symbol, name) VALUES ('TEST', 'Test Asset')"
    )
    conn.execute(
        "INSERT INTO portfolios (name, initial_capital) VALUES ('Test', 100000)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO trades (portfolio_id, asset_id, side, quantity, price, is_simulated) "
            "VALUES (1, 1, 'buy', 10, 100.0, 0)"
        )
