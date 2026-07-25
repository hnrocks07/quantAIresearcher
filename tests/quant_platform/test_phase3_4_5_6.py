"""Phase 3-6 tests — research engine, paper broker, trading executor, risk manager."""

import os
import json
import asyncio
import pytest
from datetime import datetime, timezone, timedelta

os.environ["QP_DB_URL"] = "sqlite://"

from quant_platform.database import get_engine, Base, get_db, reset_engine
from quant_platform.models import (
    AssetORM, OHLCVORM, StrategyORM, BacktestResultORM,
    PortfolioORM, PositionORM, TradeORM, StrategyStatus,
)
from quant_platform.plugins.broker import FeeSchedule
from quant_platform.trading.paper_broker import PaperBroker
from quant_platform.trading.executor import TradingExecutor
from quant_platform.risk.manager import RiskManager


@pytest.fixture(autouse=True)
def setup_db():
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    reset_engine()


def _seed_data():
    with get_db() as db:
        a = AssetORM(symbol="TEST.NS", name="Test", asset_type="equity", exchange="NSE", market_profile="nse_equity")
        db.add(a)
        db.flush()
        asset_id = a.id
        import math
        for i in range(200):
            dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
            price = 100 + 20 * math.sin(i * 0.1)
            db.add(OHLCVORM(
                asset_id=asset_id, date=dt,
                open=price, high=price + 2, low=price - 2,
                close=price, adj_close=price, volume=50000,
            ))
        db.flush()
        return asset_id


# --- Paper Broker ---

class TestPaperBroker:
    def test_initial_state(self):
        b = PaperBroker(initial_balance=500000)
        assert b.name() == "paper"
        assert isinstance(b.fee_schedule(), FeeSchedule)

    def test_connect_disconnect(self):
        b = PaperBroker()
        asyncio.run(b.connect())
        asyncio.run(b.disconnect())

    def test_buy_order(self):
        b = PaperBroker(initial_balance=100000)
        b.set_price("TEST.NS", 100.0)
        result = asyncio.run(b.place_order("TEST.NS", "buy", 10, "market"))
        assert result.status == "filled"
        assert result.filled_qty == 10
        bal = asyncio.run(b.balance())
        assert bal["cash"] < 100000

    def test_sell_order(self):
        b = PaperBroker(initial_balance=100000)
        b.set_price("TEST.NS", 100.0)
        asyncio.run(b.place_order("TEST.NS", "buy", 10, "market"))
        b.set_price("TEST.NS", 110.0)
        result = asyncio.run(b.place_order("TEST.NS", "sell", 10, "market"))
        assert result.status == "filled"
        bal = asyncio.run(b.balance())
        assert bal["pnl"] > 0

    def test_insufficient_balance(self):
        b = PaperBroker(initial_balance=100)
        b.set_price("TEST.NS", 1000.0)
        result = asyncio.run(b.place_order("TEST.NS", "buy", 10, "market"))
        assert result.status == "rejected"

    def test_no_price_rejected(self):
        b = PaperBroker()
        result = asyncio.run(b.place_order("UNKNOWN", "buy", 10, "market"))
        assert result.status == "rejected"

    def test_positions_tracking(self):
        b = PaperBroker(initial_balance=100000)
        b.set_price("A.NS", 50.0)
        b.set_price("B.NS", 100.0)
        asyncio.run(b.place_order("A.NS", "buy", 20, "market"))
        asyncio.run(b.place_order("B.NS", "buy", 10, "market"))
        positions = asyncio.run(b.positions())
        assert len(positions) == 2

    def test_quote(self):
        b = PaperBroker()
        b.set_price("TEST.NS", 150.0)
        q = asyncio.run(b.quote("TEST.NS"))
        assert q["last"] == 150.0

    def test_order_status(self):
        b = PaperBroker(initial_balance=100000)
        b.set_price("TEST.NS", 100.0)
        result = asyncio.run(b.place_order("TEST.NS", "buy", 5, "market"))
        status = asyncio.run(b.order_status(result.order_id))
        assert status["status"] == "filled"

    def test_fee_schedule_applied(self):
        fee = FeeSchedule(commission_pct=0.01)
        b = PaperBroker(initial_balance=100000, fee_schedule=fee)
        b.set_price("TEST.NS", 100.0)
        asyncio.run(b.place_order("TEST.NS", "buy", 100, "market"))
        bal = asyncio.run(b.balance())
        assert bal["cash"] < 100000 - 10000

    def test_full_sell_removes_position(self):
        b = PaperBroker(initial_balance=100000)
        b.set_price("TEST.NS", 100.0)
        asyncio.run(b.place_order("TEST.NS", "buy", 10, "market"))
        asyncio.run(b.place_order("TEST.NS", "sell", 10, "market"))
        positions = asyncio.run(b.positions())
        assert len(positions) == 0


# --- Risk Manager ---

class TestRiskManager:
    def test_health_no_strategies(self):
        rm = RiskManager()
        h = rm.portfolio_health()
        assert h["status"] == "no_active_strategies"
        assert h["strategies"] == 0

    def test_health_with_strategies(self):
        with get_db() as db:
            db.add(StrategyORM(
                name="risk_test_1", status=StrategyStatus.SHORTLISTED.value,
                win_rate=0.85, max_drawdown=0.05, net_profit_after_fees=5000,
                sharpe_ratio=2.0, profit_factor=3.0,
            ))
            db.add(StrategyORM(
                name="risk_test_2", status=StrategyStatus.SHORTLISTED.value,
                win_rate=0.75, max_drawdown=0.08, net_profit_after_fees=3000,
                sharpe_ratio=1.5, profit_factor=2.0,
            ))
            db.add(StrategyORM(
                name="risk_test_3", status=StrategyStatus.SHORTLISTED.value,
                win_rate=0.90, max_drawdown=0.03, net_profit_after_fees=8000,
                sharpe_ratio=3.0, profit_factor=5.0,
            ))
            db.flush()

        rm = RiskManager()
        h = rm.portfolio_health()
        assert h["strategies"] == 3
        assert h["diversified"] is True

    def test_correlation_empty(self):
        rm = RiskManager()
        c = rm.correlation_matrix()
        assert c["matrix"] == []

    def test_correlation_with_data(self):
        a = _seed_data()
        with get_db() as db:
            s1 = StrategyORM(name="corr_1", status=StrategyStatus.SCORED.value)
            s2 = StrategyORM(name="corr_2", status=StrategyStatus.SCORED.value)
            db.add(s1)
            db.add(s2)
            db.flush()
            db.add(BacktestResultORM(
                strategy_id=s1.id, asset_id=a,
                start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
                total_trades=10, winning_trades=7, losing_trades=3,
                net_profit=5000, gross_profit=6000, total_fees=1000,
            ))
            db.add(BacktestResultORM(
                strategy_id=s2.id, asset_id=a,
                start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
                total_trades=10, winning_trades=4, losing_trades=6,
                net_profit=-1000, gross_profit=500, total_fees=1500,
            ))
            db.flush()

        rm = RiskManager()
        c = rm.correlation_matrix([s1.id, s2.id])
        assert len(c["labels"]) == 2

    def test_stress_test_bearish(self):
        with get_db() as db:
            db.add(StrategyORM(
                name="stress_1", status=StrategyStatus.SHORTLISTED.value,
                net_profit_after_fees=10000, max_drawdown=0.05,
            ))
            db.flush()

        rm = RiskManager()
        result = rm.stress_test("bearish")
        assert result["regime"] == "bearish"
        assert result["total_strategies"] == 1

    def test_stress_test_bullish(self):
        with get_db() as db:
            db.add(StrategyORM(
                name="stress_bull", status=StrategyStatus.SHORTLISTED.value,
                net_profit_after_fees=10000, max_drawdown=0.05,
            ))
            db.flush()

        rm = RiskManager()
        result = rm.stress_test("bullish")
        assert result["total_stressed_pnl"] > 0

    def test_promote_demote(self):
        with get_db() as db:
            db.add(StrategyORM(
                name="promote_me", status=StrategyStatus.PAPER_TRADING.value,
                win_rate=0.85, net_profit_after_fees=10000, max_drawdown=0.05,
            ))
            db.add(StrategyORM(
                name="demote_me", status=StrategyStatus.PAPER_TRADING.value,
                win_rate=0.30, net_profit_after_fees=-5000, max_drawdown=0.25,
            ))
            db.flush()

        rm = RiskManager()
        result = rm.promote_or_demote()
        assert "promote_me" in result["promoted"]
        assert "demote_me" in result["demoted"]

        with get_db() as db:
            promoted = db.query(StrategyORM).filter(StrategyORM.name == "promote_me").first()
            assert promoted.status == StrategyStatus.PROMOTED.value
            demoted = db.query(StrategyORM).filter(StrategyORM.name == "demote_me").first()
            assert demoted.status == StrategyStatus.DEMOTED.value


# --- API Integration Tests ---

class TestPhase2API:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from quant_platform.api.app import app
        return TestClient(app)

    def test_profiles_list(self, client):
        r = client.get("/profiles")
        assert r.status_code == 200
        data = r.json()
        assert "nse_equity" in data

    def test_profile_detail(self, client):
        r = client.get("/profiles/nse_equity")
        assert r.status_code == 200
        assert r.json()["currency"] == "INR"

    def test_profile_not_found(self, client):
        r = client.get("/profiles/nonexistent")
        assert r.status_code == 200
        assert "error" in r.json()

    def test_assets_empty(self, client):
        r = client.get("/assets")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_strategies_empty(self, client):
        r = client.get("/strategies")
        assert r.status_code == 200
        assert r.json() == []

    def test_ingest_status(self, client):
        r = client.get("/ingest/status")
        assert r.status_code == 200
        assert r.json()["status"] == "idle"

    def test_research_status(self, client):
        r = client.get("/research/status")
        assert r.status_code == 200
        assert r.json()["status"] == "idle"

    def test_trading_status(self, client):
        r = client.get("/trading/status")
        assert r.status_code == 200
        assert r.json()["status"] == "idle"

    def test_risk_health(self, client):
        r = client.get("/risk/health")
        assert r.status_code == 200

    def test_risk_correlation(self, client):
        r = client.get("/risk/correlation")
        assert r.status_code == 200

    def test_stress_test(self, client):
        r = client.get("/risk/stress-test?regime=bearish")
        assert r.status_code == 200

    def test_scoring_rank(self, client):
        r = client.get("/scoring/rank")
        assert r.status_code == 200

    def test_portfolios_empty(self, client):
        r = client.get("/portfolios")
        assert r.status_code == 200
