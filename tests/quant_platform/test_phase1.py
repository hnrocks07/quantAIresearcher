"""Phase 1 tests — platform foundation: DB, API, plugins, kill switch, events, logging."""

import asyncio
import json
import os
import pytest
from unittest.mock import patch

os.environ["QP_DB_URL"] = "sqlite://"
os.environ["QP_LOG_FORMAT"] = "text"

from quant_platform.config import Settings, RunMode, get_settings, reset_settings
from quant_platform.database import Base, get_engine, get_db, reset_engine
from quant_platform.models import (
    AssetORM, OHLCVORM, PortfolioORM, PositionORM, TradeORM,
    StrategyORM, BacktestResultORM, KillSwitchStateORM, SystemEventORM,
    AssetSchema, PortfolioSchema, PositionSchema, TradeSchema, StrategySchema,
    AssetType, Side, PositionStatus, OrderType, StrategyStatus,
)
from quant_platform.plugins.broker import BrokerAdapter, FeeSchedule, OrderResult
from quant_platform.plugins.research import ResearchSource, ImportedStrategy
from quant_platform.plugins.llm import LLMProvider, LLMResponse
from quant_platform.plugins.registry import PluginRegistry
from quant_platform.kill_switch import KillSwitch
from quant_platform.event_bus import EventBus, Event
from quant_platform.logging import JSONFormatter, AuditLogger, setup_logging


@pytest.fixture(autouse=True)
def clean_db():
    reset_settings()
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    reset_engine()


# --- Config ---

class TestConfig:
    def test_defaults(self):
        s = Settings(db_url="sqlite:///:memory:")
        assert s.run_mode == RunMode.LOCAL
        assert s.real_trading is False
        assert s.log_level == "INFO"
        assert s.kill_switch_heartbeat_timeout == 15

    def test_run_modes(self):
        assert RunMode.LOCAL.value == "local"
        assert RunMode.SERVER.value == "server"

    def test_env_override(self):
        with patch.dict(os.environ, {"QP_RUN_MODE": "server"}):
            reset_settings()
            s = get_settings()
            assert s.run_mode == RunMode.SERVER
            reset_settings()


# --- SQLAlchemy ORM ---

class TestORM:
    def test_create_asset(self):
        with get_db() as db:
            asset = AssetORM(symbol="RELIANCE", name="Reliance Industries", asset_type="equity", exchange="NSE")
            db.add(asset)
            db.flush()
            assert asset.id is not None
            assert asset.symbol == "RELIANCE"

    def test_create_portfolio(self):
        with get_db() as db:
            p = PortfolioORM(name="Test Portfolio", initial_capital=100000.0)
            db.add(p)
            db.flush()
            assert p.id is not None

    def test_create_strategy(self):
        with get_db() as db:
            s = StrategyORM(name="RSI Crossover", source="tradingview", status="discovered")
            db.add(s)
            db.flush()
            assert s.id is not None
            assert s.status == "discovered"

    def test_create_ohlcv(self):
        from datetime import datetime, timezone
        with get_db() as db:
            asset = AssetORM(symbol="TCS", name="TCS Ltd", asset_type="equity")
            db.add(asset)
            db.flush()
            ohlcv = OHLCVORM(
                asset_id=asset.id, date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                open=3500.0, high=3550.0, low=3480.0, close=3520.0, adj_close=3520.0, volume=1000000
            )
            db.add(ohlcv)
            db.flush()
            assert ohlcv.id is not None

    def test_create_trade(self):
        with get_db() as db:
            p = PortfolioORM(name="Trade Portfolio", initial_capital=50000.0)
            a = AssetORM(symbol="INFY", name="Infosys", asset_type="equity")
            db.add_all([p, a])
            db.flush()
            t = TradeORM(portfolio_id=p.id, asset_id=a.id, side="buy", quantity=10, price=1500.0, is_simulated=True)
            db.add(t)
            db.flush()
            assert t.id is not None

    def test_backtest_result(self):
        from datetime import datetime, timezone
        with get_db() as db:
            s = StrategyORM(name="MACD Strategy", source="manual")
            a = AssetORM(symbol="NIFTY50", name="NIFTY 50", asset_type="index")
            db.add_all([s, a])
            db.flush()
            bt = BacktestResultORM(
                strategy_id=s.id, asset_id=a.id,
                start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
                total_trades=100, winning_trades=82, losing_trades=18,
                win_rate=0.82, gross_profit=150000.0, total_fees=5000.0, net_profit=145000.0,
            )
            db.add(bt)
            db.flush()
            assert bt.win_rate == 0.82
            assert bt.net_profit == 145000.0

    def test_system_event(self):
        with get_db() as db:
            ev = SystemEventORM(event_type="kill_switch.triggered", source="api", payload='{"reason":"test"}')
            db.add(ev)
            db.flush()
            assert ev.id is not None

    def test_all_tables_created(self):
        engine = get_engine()
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = ["assets", "ohlcv", "portfolios", "positions", "trades", "strategies", "backtest_results", "kill_switch_state", "system_events"]
        for t in expected:
            assert t in tables, f"Table {t} missing"


# --- Pydantic Schemas ---

class TestSchemas:
    def test_asset_schema_validation(self):
        a = AssetSchema(symbol="  reliance  ", name="Reliance")
        assert a.symbol == "RELIANCE"

    def test_asset_schema_empty_symbol(self):
        with pytest.raises(ValueError):
            AssetSchema(symbol="  ", name="test")

    def test_portfolio_schema(self):
        p = PortfolioSchema(name="My Portfolio", initial_capital=100000)
        assert p.name == "My Portfolio"

    def test_portfolio_negative_capital(self):
        with pytest.raises(ValueError):
            PortfolioSchema(name="test", initial_capital=-1)

    def test_position_pnl(self):
        p = PositionSchema(portfolio_id=1, asset_id=1, quantity=10, avg_entry_price=100, current_price=110, side=Side.LONG)
        assert p.unrealized_pnl == 100.0

    def test_position_short_pnl(self):
        p = PositionSchema(portfolio_id=1, asset_id=1, quantity=10, avg_entry_price=100, current_price=90, side=Side.SHORT)
        assert p.unrealized_pnl == 100.0

    def test_trade_total_cost(self):
        t = TradeSchema(portfolio_id=1, asset_id=1, side=Side.BUY, quantity=10, price=100, commission=20, slippage=5)
        assert t.total_cost == 1025.0

    def test_strategy_schema(self):
        s = StrategySchema(name="RSI Cross", source="tradingview", status=StrategyStatus.DISCOVERED)
        assert s.is_original is False
        assert s.is_publishable is False

    def test_all_enums(self):
        assert AssetType.CRYPTO.value == "crypto"
        assert AssetType.COMMODITY.value == "commodity"
        assert StrategyStatus.PAPER_TRADING.value == "paper_trading"
        assert StrategyStatus.PROMOTED.value == "promoted"


# --- Fee Schedule ---

class TestFeeSchedule:
    def test_zero_fees(self):
        fs = FeeSchedule()
        assert fs.calculate_total_fees(100000, "buy") == 0.0

    def test_commission_only(self):
        fs = FeeSchedule(commission_per_order=20.0)
        assert fs.calculate_total_fees(100000, "buy") == 20.0

    def test_full_nse_fees(self):
        fs = FeeSchedule(
            commission_per_order=20.0,
            commission_pct=0.0003,
            stt_pct=0.001,
            exchange_charge_pct=0.0000345,
            sebi_charge_pct=0.000001,
            stamp_duty_pct=0.00015,
        )
        sell_fees = fs.calculate_total_fees(100000, "sell")
        assert sell_fees > 100


# --- Plugin Registry ---

class TestPluginRegistry:
    def test_register_and_get_broker(self):
        reg = PluginRegistry()

        class DummyBroker(BrokerAdapter):
            def name(self): return "dummy"
            def fee_schedule(self): return FeeSchedule()
            async def connect(self): pass
            async def disconnect(self): pass
            async def place_order(self, *a, **k): return OrderResult("1", "filled")
            async def cancel_order(self, *a): return True
            async def order_status(self, *a): return {}
            async def positions(self): return []
            async def balance(self): return {"cash": 100000}
            async def quote(self, *a): return {"last": 100}

        reg.register_broker("dummy", DummyBroker)
        broker = reg.get_broker("dummy")
        assert broker.name() == "dummy"
        assert "dummy" in reg.list_brokers()

    def test_missing_broker_raises(self):
        reg = PluginRegistry()
        with pytest.raises(KeyError):
            reg.get_broker("nonexistent")

    def test_register_llm(self):
        reg = PluginRegistry()

        class DummyLLM(LLMProvider):
            def name(self): return "dummy"
            async def generate(self, *a, **k): return LLMResponse(content="hi", model="dummy")
            async def generate_json(self, *a, **k): return {"result": "ok"}

        reg.register_llm("dummy", DummyLLM)
        assert "dummy" in reg.list_llm()


# --- Kill Switch ---

class TestKillSwitch:
    def test_initial_state(self):
        ks = KillSwitch()
        assert ks.is_active is False
        assert ks.is_safe_to_trade is True

    def test_trigger(self):
        ks = KillSwitch()
        asyncio.run(ks.trigger("test", "unit test"))
        assert ks.is_active is True
        assert ks.is_safe_to_trade is False

    def test_reset(self):
        ks = KillSwitch()
        asyncio.run(ks.trigger("test", "reason"))
        asyncio.run(ks.reset("test"))
        assert ks.is_active is False
        assert ks.is_safe_to_trade is True

    def test_check_or_raise(self):
        ks = KillSwitch()
        asyncio.run(ks.trigger("test", "reason"))
        with pytest.raises(RuntimeError, match="Kill switch active"):
            ks.check_or_raise("place_order")

    def test_heartbeat(self):
        ks = KillSwitch()
        ks.heartbeat()
        assert ks.is_safe_to_trade is True

    def test_status(self):
        ks = KillSwitch()
        status = ks.status()
        assert "is_active" in status
        assert "heartbeat_age_seconds" in status
        assert "history" in status


# --- Event Bus ---

class TestEventBus:
    def test_publish_and_recent(self):
        bus = EventBus()
        asyncio.run(
            bus.emit("test.event", "unit_test", key="value")
        )
        events = bus.recent(limit=10)
        assert len(events) == 1
        assert events[0].event_type == "test.event"
        assert events[0].payload["key"] == "value"

    def test_subscribe(self):
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("my.event", handler)
        asyncio.run(bus.emit("my.event", "test"))
        assert len(received) == 1

    def test_subscribe_all(self):
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe_all(handler)
        asyncio.run(bus.emit("a", "test"))
        asyncio.run(bus.emit("b", "test"))
        assert len(received) == 2

    def test_filter_by_type(self):
        bus = EventBus()
        asyncio.run(bus.emit("alpha", "test"))
        asyncio.run(bus.emit("beta", "test"))
        asyncio.run(bus.emit("alpha", "test"))
        assert len(bus.recent(event_type="alpha")) == 2

    def test_event_serialization(self):
        e = Event(event_type="test", source="unit", payload={"x": 1})
        d = e.to_dict()
        assert d["event_type"] == "test"
        j = e.to_json()
        parsed = json.loads(j)
        assert parsed["source"] == "unit"

    def test_clear(self):
        bus = EventBus()
        asyncio.run(bus.emit("test", "src"))
        bus.clear()
        assert len(bus.recent()) == 0


# --- Logging ---

class TestLogging:
    def test_json_formatter(self):
        import logging
        fmt = JSONFormatter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello"
        assert parsed["level"] == "INFO"

    def test_setup_logging(self):
        setup_logging()
        import logging
        logger = logging.getLogger("quant")
        assert len(logger.handlers) >= 1


# --- FastAPI (using test client) ---

class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from quant_platform.api.app import app
        with TestClient(app) as c:
            yield c

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "kill_switch" in data
        assert "run_mode" in data

    def test_kill_switch_trigger(self, client):
        r = client.post("/kill-switch/trigger?reason=test")
        assert r.status_code == 200
        assert r.json()["status"] == "triggered"

    def test_kill_switch_status(self, client):
        r = client.get("/kill-switch/status")
        assert r.status_code == 200
        assert "is_active" in r.json()

    def test_kill_switch_reset(self, client):
        client.post("/kill-switch/trigger?reason=test")
        r = client.post("/kill-switch/reset")
        assert r.status_code == 200

    def test_heartbeat(self, client):
        r = client.post("/kill-switch/heartbeat")
        assert r.status_code == 200

    def test_recent_events(self, client):
        r = client.get("/events/recent")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_config_endpoint(self, client):
        r = client.get("/config")
        assert r.status_code == 200
        data = r.json()
        assert "run_mode" in data
        assert "real_trading" in data
        assert data["real_trading"] is False
