-- Migration 001: Initial Schema for Local Trading Simulator
-- Database: SQLite
-- Phase: 0
-- Idempotent: Yes (uses IF NOT EXISTS throughout)

CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    asset_type      TEXT    NOT NULL DEFAULT 'equity',  -- equity, index, futures, options
    exchange        TEXT    NOT NULL DEFAULT 'NSE',
    currency        TEXT    NOT NULL DEFAULT 'INR',
    lot_size        INTEGER NOT NULL DEFAULT 1,
    tick_size       REAL    NOT NULL DEFAULT 0.05,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (asset_type IN ('equity', 'index', 'futures', 'options')),
    CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS portfolios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    description     TEXT    NOT NULL DEFAULT '',
    initial_capital REAL    NOT NULL DEFAULT 0.0,
    currency        TEXT    NOT NULL DEFAULT 'INR',
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (initial_capital >= 0),
    CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    quantity        REAL    NOT NULL DEFAULT 0.0,
    avg_entry_price REAL    NOT NULL DEFAULT 0.0,
    current_price   REAL    NOT NULL DEFAULT 0.0,
    side            TEXT    NOT NULL DEFAULT 'long',  -- long, short
    status          TEXT    NOT NULL DEFAULT 'open',  -- open, closed
    opened_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    closed_at       TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id),
    FOREIGN KEY (asset_id)     REFERENCES assets(id),
    CHECK (side IN ('long', 'short')),
    CHECK (status IN ('open', 'closed')),
    CHECK (avg_entry_price >= 0),
    CHECK (current_price >= 0)
);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL,
    asset_id        INTEGER NOT NULL,
    position_id     INTEGER,
    side            TEXT    NOT NULL,  -- buy, sell
    quantity        REAL    NOT NULL,
    price           REAL    NOT NULL,
    commission      REAL    NOT NULL DEFAULT 0.0,
    slippage        REAL    NOT NULL DEFAULT 0.0,
    order_type      TEXT    NOT NULL DEFAULT 'market',  -- market, limit, stop
    is_simulated    INTEGER NOT NULL DEFAULT 1,  -- ALWAYS 1: real trading disabled
    executed_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    notes           TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id),
    FOREIGN KEY (asset_id)     REFERENCES assets(id),
    FOREIGN KEY (position_id)  REFERENCES positions(id),
    CHECK (side IN ('buy', 'sell')),
    CHECK (quantity > 0),
    CHECK (price >= 0),
    CHECK (commission >= 0),
    CHECK (slippage >= 0),
    CHECK (order_type IN ('market', 'limit', 'stop')),
    CHECK (is_simulated = 1)  -- enforced: no real trading
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_positions_asset     ON positions(asset_id);
CREATE INDEX IF NOT EXISTS idx_positions_status    ON positions(status);
CREATE INDEX IF NOT EXISTS idx_trades_portfolio    ON trades(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_trades_asset        ON trades(asset_id);
CREATE INDEX IF NOT EXISTS idx_trades_executed     ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_assets_symbol       ON assets(symbol);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_versions (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL DEFAULT ''
);

INSERT OR IGNORE INTO schema_versions (version, description)
VALUES (1, 'Initial schema: assets, portfolios, positions, trades');
