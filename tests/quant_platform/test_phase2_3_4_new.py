"""Tests for Phases 2, 3, 4 — F&O fields, research integration, broker."""

from __future__ import annotations

import json
import os
import math
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("QP_DB_URL", "sqlite:///test_phase234.db")

from quant_platform.database import Base, reset_engine, get_engine, get_db
from quant_platform.models import (
    AssetORM, AssetType, StrategyORM, StrategyStatus, SystemEventORM,
)
from quant_platform.research.position_sizing import calculate_position_size
from quant_platform.research.stop_loss import calculate_optimal_sl
from quant_platform.research.regime import classify_regime, classify_history
from quant_platform.research.combination import combine_strategies, generate_combinations
from quant_platform.research.pine_export import export_to_pine
from quant_platform.research.activity_log import ResearchActivityLog
from quant_platform.research.tradingview_webhook import process_webhook
from quant_platform.research.strategies import SignalResult, sma_crossover
from quant_platform.trading.angel_broker import AngelBroker
from quant_platform.trading.decision_log import TradeDecisionLog


@pytest.fixture(autouse=True)
def setup_db():
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    reset_engine()


# --- Phase 2: F&O Fields ---

def test_asset_fno_columns_exist():
    engine = get_engine()
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("assets")}
    assert "expiry_date" in columns
    assert "strike_price" in columns
    assert "option_type" in columns
    assert "contract_type" in columns


def test_asset_fno_fields_writable():
    with get_db() as db:
        asset = AssetORM(
            symbol="NIFTY25JUL",
            name="NIFTY Jul Futures",
            asset_type="futures",
            exchange="NSE",
            market_profile="nse_fno",
            expiry_date=datetime(2025, 7, 31, tzinfo=timezone.utc),
            strike_price=24000.0,
            option_type="CE",
            contract_type="futures",
        )
        db.add(asset)
        db.flush()
        assert asset.id is not None
        assert asset.strike_price == 24000.0
        assert asset.option_type == "CE"


def test_asset_type_enum_has_futures_options():
    assert AssetType.FUTURES.value == "futures"
    assert AssetType.OPTIONS.value == "options"


def test_nse_fno_profile_exists():
    import json
    from pathlib import Path
    profile_path = Path(__file__).resolve().parents[2] / "src" / "quant_platform" / "market_profiles" / "configs" / "nse_fno.json"
    assert profile_path.exists()
    data = json.loads(profile_path.read_text())
    assert data["name"] == "nse_fno"
    assert data["currency"] == "INR"
    assert len(data["instruments"]) == 2


# --- Phase 3: Position Sizing ---

def test_position_sizing_basic():
    prices = [100.0 + i * 0.5 for i in range(50)]
    result = calculate_position_size(prices, 100000.0, risk_pct=0.02)
    assert "position_size" in result
    assert "risk_per_trade" in result
    assert "atr" in result
    assert "stop_distance" in result
    assert result["risk_per_trade"] == 2000.0
    assert result["position_size"] > 0


def test_position_sizing_insufficient_data():
    result = calculate_position_size([100.0, 101.0], 100000.0)
    assert result["position_size"] == 0


# --- Phase 3: Stop Loss ---

def test_stop_loss_basic():
    prices = [100.0 + i * 0.3 for i in range(30)]
    result = calculate_optimal_sl(prices)
    assert result["method"] == "atr"
    assert result["atr"] > 0
    assert result["sl_price"] < prices[-1]
    assert 0 < result["sl_pct"] < 1


def test_stop_loss_insufficient_data():
    result = calculate_optimal_sl([100.0, 101.0], period=14)
    assert result["atr"] == 0.0


# --- Phase 3: Regime ---

def test_regime_bullish():
    prices = [100.0 + i * 2 for i in range(100)]
    r = classify_regime(prices, window=20)
    assert r == "bullish"


def test_regime_bearish():
    prices = [200.0 - i * 2 for i in range(100)]
    r = classify_regime(prices, window=20)
    assert r == "bearish"


def test_regime_history():
    prices = [100.0 + i for i in range(100)]
    dates = [f"2025-01-{i+1:02d}" for i in range(100)]
    history = classify_history(prices, dates, window=20)
    assert len(history) > 0
    assert "date" in history[0]
    assert "regime" in history[0]


# --- Phase 3: Combination ---

def test_combine_strategies():
    sig_a = SignalResult(
        entries=[True, False, True, False],
        exits=[False, True, False, True],
        name="a",
        parameters={},
    )
    sig_b = SignalResult(
        entries=[True, True, False, False],
        exits=[False, False, True, False],
        name="b",
        parameters={},
    )
    combined = combine_strategies(sig_a, sig_b)
    assert combined.entries == [True, False, False, False]
    assert combined.exits == [False, True, True, True]
    assert "a+b" in combined.name


def test_generate_combinations():
    strategies = {"a": None, "b": None, "c": None}
    combos = generate_combinations(strategies)
    assert len(combos) == 3
    assert ("a", "b") in combos


# --- Phase 3: Pine Export ---

def test_pine_export_sma():
    pine = export_to_pine("test_sma", {"fast": 10, "slow": 30}, "sma_crossover")
    assert "//@version=5" in pine
    assert "strategy(" in pine
    assert "ta.sma" in pine


def test_pine_export_rsi():
    pine = export_to_pine("test_rsi", {"period": 14}, "rsi")
    assert "ta.rsi" in pine


def test_pine_export_macd():
    pine = export_to_pine("test_macd", {}, "macd")
    assert "ta.macd" in pine


# --- Phase 3: Activity Log ---

def test_activity_log():
    log = ResearchActivityLog()
    log.log_action("test", "strat1", "detail", "reason")
    entries = log.get_log()
    assert len(entries) == 1
    assert entries[0]["action"] == "test"
    assert entries[0]["strategy"] == "strat1"
    log.clear()
    assert len(log.get_log()) == 0


# --- Phase 3: Webhook ---

def test_webhook_accept():
    payload = {
        "strategy_name": "tv_alert_test",
        "action": "buy",
        "ticker": "RELIANCE",
        "price": 2500.0,
        "timeframe": "1D",
    }
    result = process_webhook(payload)
    assert result["status"] == "accepted"
    assert result["strategy"] == "tv_alert_test"


def test_webhook_reject_bad_secret():
    result = process_webhook({}, secret="abc", provided_secret="wrong")
    assert result["status"] == "rejected"


def test_webhook_reject_bad_action():
    result = process_webhook({"action": "hold"})
    assert result["status"] == "rejected"


# --- Phase 4: AngelBroker ---

def test_angel_broker_fee_schedule():
    broker = AngelBroker()
    fees = broker.fee_schedule()
    assert fees.commission_per_order == 20.0
    assert fees.stt_pct == 0.001
    assert fees.gst_pct == 0.18


def test_angel_broker_name():
    broker = AngelBroker()
    assert broker.name() == "angel"


# --- Phase 4: TradeDecisionLog ---

def test_trade_decision_log():
    tdl = TradeDecisionLog()
    tdl.log_decision(
        signal="buy",
        reasoning="RSI oversold",
        action="place_order",
        result="success",
        strategy_id=1,
        asset_id=1,
    )
    decisions = tdl.get_decisions(limit=10)
    assert len(decisions) >= 1
    assert decisions[0]["signal"] == "buy"
    assert decisions[0]["reasoning"] == "RSI oversold"


# --- Phase 4: API Endpoints ---

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from quant_platform.api.app import app
    return TestClient(app)


def test_webhook_endpoint(client):
    resp = client.post("/webhooks/tradingview", json={
        "strategy_name": "api_test",
        "action": "sell",
        "ticker": "TCS",
        "price": 3500.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"


def test_activity_log_endpoint(client):
    resp = client.get("/research/activity-log")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
