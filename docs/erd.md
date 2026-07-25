# Entity Relationship Diagram — Schema v0

Phase 0 initial schema for Local Trading Simulator.
All trades are simulated (is_simulated = 1 enforced by CHECK constraint).

## Entities

    assets
    ------
    id           INTEGER PK AUTOINCREMENT
    symbol       TEXT UNIQUE NOT NULL
    name         TEXT NOT NULL
    asset_type   TEXT (equity|index|futures|options)
    exchange     TEXT (default NSE)
    currency     TEXT (default INR)
    lot_size     INTEGER
    tick_size    REAL
    is_active    INTEGER (0|1)
    created_at   TEXT
    updated_at   TEXT

    portfolios
    ----------
    id              INTEGER PK AUTOINCREMENT
    name            TEXT UNIQUE NOT NULL
    description     TEXT
    initial_capital REAL (>= 0)
    currency        TEXT (default INR)
    is_active       INTEGER (0|1)
    created_at      TEXT
    updated_at      TEXT

    positions
    ---------
    id              INTEGER PK AUTOINCREMENT
    portfolio_id    INTEGER FK -> portfolios.id
    asset_id        INTEGER FK -> assets.id
    quantity        REAL
    avg_entry_price REAL
    current_price   REAL
    side            TEXT (long|short)
    status          TEXT (open|closed)
    opened_at       TEXT
    closed_at       TEXT
    updated_at      TEXT

    trades
    ------
    id              INTEGER PK AUTOINCREMENT
    portfolio_id    INTEGER FK -> portfolios.id
    asset_id        INTEGER FK -> assets.id
    position_id     INTEGER FK -> positions.id (nullable)
    side            TEXT (buy|sell)
    quantity        REAL (> 0)
    price           REAL (>= 0)
    commission      REAL (>= 0)
    slippage        REAL (>= 0)
    order_type      TEXT (market|limit|stop)
    is_simulated    INTEGER (ALWAYS 1)
    executed_at     TEXT
    created_at      TEXT
    notes           TEXT

## Relationships

    portfolios  1 --- * positions   (portfolio_id FK)
    assets      1 --- * positions   (asset_id FK)
    portfolios  1 --- * trades      (portfolio_id FK)
    assets      1 --- * trades      (asset_id FK)
    positions   1 --- * trades      (position_id FK, nullable)

## Constraints

- trades.is_simulated CHECK = 1 — real trading permanently disabled
- assets.symbol UNIQUE — no duplicate tickers
- portfolios.name UNIQUE — no duplicate portfolio names
- All prices and quantities have non-negative CHECK constraints
