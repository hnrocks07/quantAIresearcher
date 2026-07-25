# Local Trading Simulator

A local-first quant research and strategy platform for Indian markets
(NIFTY, BANKNIFTY, FINNIFTY, NSE equities). Simulation only — real
trading is permanently disabled.

Built as part of an engineering case study measuring whether AI agent
teams can produce production-grade software.

## Prerequisites

- Python 3.11+
- pip (or uv)

## Setup

    git clone <repo-url>
    cd AI_Quant_AgentTeam_Proof_ProductionGrade_Bootstrap

    python -m venv .venv
    source .venv/bin/activate

    pip install -e ".[dev]"

    cp .env.example .env

## Run Tests

    pytest -v

This runs both the agent system tests and quant platform model tests.

## Project Structure

    src/
      agent_system/     — autonomous AI engineering agent pipeline
      quant_platform/   — the trading simulator being built
        config.py       — env-var based configuration (QP_ prefix)
        models.py       — Asset, Portfolio, Position, Trade
        database.py     — SQLite connection and migrations
    migrations/         — SQL migration scripts (idempotent)
    tests/              — pytest test suite
    docs/               — architecture decisions, ERD, phase audits
    phases/             — phase specifications for agent system

## Configuration

All settings load from environment variables with QP_ prefix.
See .env.example for defaults. No secrets are committed to source.

## Storage

SQLite by default (data/trading.db). See docs/adr/001-local-first-storage.md
for rationale and future migration path to PostgreSQL.

## Safety

- real_trading is False by default and enforced by CHECK constraint in DB
- Trade.is_simulated must be True (Pydantic validator rejects False)
- No secrets in source — .env is gitignored
