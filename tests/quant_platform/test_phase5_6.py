"""Phase 5 & 6 tests — agents, automation, review, risk monitoring."""

import os
import json
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("QP_DB_URL", "sqlite://")

from quant_platform.database import get_engine, Base, get_db, reset_engine
from quant_platform.config import Settings, reset_settings
from quant_platform.models import (
    StrategyORM, TradeORM, PortfolioORM, AssetORM, PositionORM, StrategyStatus,
)
from quant_platform.plugins.llm import LLMProvider, LLMResponse
from quant_platform.kill_switch import KillSwitch


@pytest.fixture(autouse=True)
def setup_db():
    reset_settings()
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    reset_engine()
    reset_settings()


def _settings(**overrides):
    defaults = {
        "db_url": "sqlite://",
        "promotion_min_trades": 5,
        "promotion_win_rate": 0.6,
        "paper_trading_days_required": 7,
        "max_positions": 10,
        "max_position_per_instrument": 2,
        "daily_loss_cap_pct": 0.05,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class MockLLM(LLMProvider):
    def __init__(self, response_dict=None):
        self._response = response_dict or {}

    def name(self):
        return "mock"

    async def generate(self, prompt, system=None, temperature=0.0, max_tokens=4096):
        return LLMResponse(content=json.dumps(self._response), model="mock")

    async def generate_json(self, prompt, system=None, temperature=0.0, max_tokens=4096):
        return self._response


# ===== Phase 5: Signal Agent =====

@pytest.mark.asyncio
async def test_signal_agent_analyze():
    from quant_platform.agents.signal_agent import SignalAgent
    llm = MockLLM({"action": "buy", "confidence": 0.85, "reasoning": "Bullish", "position_size_suggestion": 0.5})
    agent = SignalAgent(llm, _settings())
    result = await agent.analyze_signal("sma_cross", {"type": "entry"}, {"regime": "bullish"})
    assert result["action"] == "buy"
    assert result["confidence"] == 0.85
    assert result["position_size_suggestion"] == 0.5


@pytest.mark.asyncio
async def test_signal_agent_fallback_on_error():
    from quant_platform.agents.signal_agent import SignalAgent
    llm = MockLLM()
    llm.generate_json = AsyncMock(side_effect=Exception("LLM down"))
    agent = SignalAgent(llm, _settings())
    result = await agent.analyze_signal("test", {}, {})
    assert result["action"] == "hold"
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_signal_agent_batch():
    from quant_platform.agents.signal_agent import SignalAgent
    llm = MockLLM({"action": "sell", "confidence": 0.7, "reasoning": "Bear", "position_size_suggestion": 0.3})
    agent = SignalAgent(llm, _settings())
    signals = [
        {"strategy_name": "s1", "signal": {}, "market_context": {}},
        {"strategy_name": "s2", "signal": {}, "market_context": {}},
    ]
    results = await agent.batch_analyze(signals)
    assert len(results) == 2
    assert all(r["action"] == "sell" for r in results)


# ===== Phase 5: Decision Agent =====

@pytest.mark.asyncio
async def test_decision_agent_approve():
    from quant_platform.agents.decision_agent import DecisionAgent
    from quant_platform.risk.manager import RiskManager
    llm = MockLLM({"approved": True, "final_action": "buy", "adjusted_size": 100.0, "reasoning": "OK", "risk_notes": []})
    agent = DecisionAgent(llm, RiskManager(), _settings())
    result = await agent.decide({"action": "buy", "confidence": 0.9}, {"cash": 100000})
    assert result["approved"] is True
    assert result["final_action"] == "buy"


@pytest.mark.asyncio
async def test_decision_agent_reject_on_error():
    from quant_platform.agents.decision_agent import DecisionAgent
    from quant_platform.risk.manager import RiskManager
    llm = MockLLM()
    llm.generate_json = AsyncMock(side_effect=Exception("fail"))
    agent = DecisionAgent(llm, RiskManager(), _settings())
    result = await agent.decide({}, {})
    assert result["approved"] is False


@pytest.mark.asyncio
async def test_decision_agent_review_portfolio():
    from quant_platform.agents.decision_agent import DecisionAgent
    from quant_platform.risk.manager import RiskManager
    llm = MockLLM({"recommendations": [{"position_id": 1, "action": "close", "reasoning": "Stop hit"}]})
    agent = DecisionAgent(llm, RiskManager(), _settings())
    result = await agent.review_portfolio([{"id": 1, "symbol": "RELIANCE"}])
    assert len(result["recommendations"]) == 1


# ===== Phase 5: Activity Feed =====

def test_activity_feed_log_and_get():
    from quant_platform.agents.activity_feed import AgentActivityFeed
    feed = AgentActivityFeed()
    feed.log("signal_agent", "analyze", {"result": "buy"}, "bullish signal")
    feed.log("decision_agent", "decide", {"approved": True})
    entries = feed.get_feed(10)
    assert len(entries) == 2
    assert entries[0]["agent_name"] == "signal_agent"


def test_activity_feed_filter_by_agent():
    from quant_platform.agents.activity_feed import AgentActivityFeed
    feed = AgentActivityFeed()
    feed.log("a1", "x", {})
    feed.log("a2", "y", {})
    feed.log("a1", "z", {})
    assert len(feed.get_by_agent("a1")) == 2
    assert len(feed.get_by_agent("a2")) == 1


def test_activity_feed_clear():
    from quant_platform.agents.activity_feed import AgentActivityFeed
    feed = AgentActivityFeed()
    feed.log("a", "b", {})
    feed.clear()
    assert len(feed.get_feed()) == 0


# ===== Phase 5: Webhook Pipeline =====

@pytest.mark.asyncio
async def test_webhook_pipeline_approved():
    from quant_platform.trading.webhook_pipeline import process_webhook_to_trade
    from quant_platform.agents.signal_agent import SignalAgent
    from quant_platform.agents.decision_agent import DecisionAgent
    from quant_platform.agents.activity_feed import AgentActivityFeed
    from quant_platform.trading.executor import TradingExecutor

    llm_signal = MockLLM({"action": "buy", "confidence": 0.9, "reasoning": "Go", "position_size_suggestion": 0.5})
    llm_decision = MockLLM({"approved": True, "final_action": "buy", "adjusted_size": 50.0, "reasoning": "OK", "risk_notes": []})

    from quant_platform.risk.manager import RiskManager
    sa = SignalAgent(llm_signal, _settings())
    da = DecisionAgent(llm_decision, RiskManager(), _settings())
    ex = TradingExecutor()
    feed = AgentActivityFeed()

    trace = await process_webhook_to_trade(
        {"strategy": "sma", "signal": {"type": "entry"}, "market_context": {}, "portfolio_state": {}},
        sa, da, ex, feed,
    )
    assert trace["decision"]["approved"] is True
    assert trace["trade_result"]["executed"] is True
    assert len(feed.get_feed()) == 3


@pytest.mark.asyncio
async def test_webhook_pipeline_rejected():
    from quant_platform.trading.webhook_pipeline import process_webhook_to_trade
    from quant_platform.agents.signal_agent import SignalAgent
    from quant_platform.agents.decision_agent import DecisionAgent
    from quant_platform.agents.activity_feed import AgentActivityFeed
    from quant_platform.trading.executor import TradingExecutor
    from quant_platform.risk.manager import RiskManager

    llm_signal = MockLLM({"action": "hold", "confidence": 0.3, "reasoning": "Weak", "position_size_suggestion": 0.0})
    llm_decision = MockLLM({"approved": False, "final_action": "hold", "adjusted_size": 0.0, "reasoning": "Nope", "risk_notes": ["Low confidence"]})

    sa = SignalAgent(llm_signal, _settings())
    da = DecisionAgent(llm_decision, RiskManager(), _settings())
    ex = TradingExecutor()
    feed = AgentActivityFeed()

    trace = await process_webhook_to_trade({"strategy": "x", "signal": {}, "market_context": {}, "portfolio_state": {}}, sa, da, ex, feed)
    assert trace["trade_result"]["executed"] is False


# ===== Phase 5: Promotion Manager =====

def test_promotion_evaluate_eligible():
    from quant_platform.trading.promotion import PromotionManager
    s = _settings(promotion_min_trades=2, promotion_win_rate=0.5, paper_trading_days_required=0)
    pm = PromotionManager(s)

    strategy = MagicMock()
    strategy.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    trades = [MagicMock(price=100, side="sell") for _ in range(5)]
    result = pm.evaluate(strategy, trades)
    assert result["eligible"] is True
    assert result["trade_count"] == 5


def test_promotion_evaluate_not_enough_trades():
    from quant_platform.trading.promotion import PromotionManager
    pm = PromotionManager(_settings(promotion_min_trades=100))
    strategy = MagicMock()
    strategy.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    result = pm.evaluate(strategy, [])
    assert result["eligible"] is False
    assert any("trades" in r.lower() for r in result["reasons"])


def test_promotion_promote_demote():
    from quant_platform.trading.promotion import PromotionManager
    pm = PromotionManager(_settings())

    with get_db() as db:
        s = StrategyORM(name="promo_test", status="paper_trading")
        db.add(s)
        db.flush()
        sid = s.id

        assert pm.promote(sid, db) is True
        db.refresh(s)
        assert s.status == "promoted"

        assert pm.demote(sid, db, "underperforming") is True
        db.refresh(s)
        assert s.status == "demoted"


# ===== Phase 5: Position Scaler =====

def test_position_scaler_winning():
    from quant_platform.trading.position_scaler import PositionScaler
    scaler = PositionScaler()
    result = scaler.scale_position(
        {"size": 100.0, "unrealized_pnl": 500.0},
        {"win_rate": 0.75, "loss_pct": 0.0},
        _settings(),
    )
    assert result["action"] == "add"
    assert result["scale_factor"] > 1.0
    assert result["suggested_size"] > 100.0


def test_position_scaler_losing():
    from quant_platform.trading.position_scaler import PositionScaler
    scaler = PositionScaler()
    result = scaler.scale_position(
        {"size": 100.0, "unrealized_pnl": -200.0},
        {"win_rate": 0.4, "loss_pct": 0.1},
        _settings(),
    )
    assert result["action"] == "reduce"
    assert result["scale_factor"] < 1.0


def test_position_scaler_hold():
    from quant_platform.trading.position_scaler import PositionScaler
    scaler = PositionScaler()
    result = scaler.scale_position(
        {"size": 100.0, "unrealized_pnl": 0.0},
        {"win_rate": 0.55, "loss_pct": 0.0},
        _settings(),
    )
    assert result["action"] == "hold"
    assert result["scale_factor"] == 1.0


# ===== Phase 6: Daily Loss Monitor =====

@pytest.mark.asyncio
async def test_daily_loss_monitor_no_breach():
    from quant_platform.risk.daily_loss_monitor import DailyLossMonitor
    ks = KillSwitch()
    monitor = DailyLossMonitor(_settings(), ks)
    trade = MagicMock()
    trade.side = "buy"
    trade.quantity = 10
    trade.price = 100
    result = await monitor.check([trade], 1000000.0)
    assert result["breached"] is False


@pytest.mark.asyncio
async def test_daily_loss_monitor_breach():
    from quant_platform.risk.daily_loss_monitor import DailyLossMonitor
    ks = KillSwitch()
    monitor = DailyLossMonitor(_settings(daily_loss_cap_pct=0.01), ks)
    trade = MagicMock()
    trade.side = "buy"
    trade.quantity = 100
    trade.price = 1000
    result = await monitor.check([trade], 100000.0)
    assert result["breached"] is True
    assert ks.is_active is True


# ===== Phase 6: Position Limiter =====

def test_position_limiter_allowed():
    from quant_platform.risk.position_limiter import PositionLimiter
    limiter = PositionLimiter(_settings(max_positions=10, max_position_per_instrument=3))
    result = limiter.can_open([{"instrument": "RELIANCE"}, {"instrument": "TCS"}], "INFY")
    assert result["allowed"] is True
    assert result["total_positions"] == 2


def test_position_limiter_denied_total():
    from quant_platform.risk.position_limiter import PositionLimiter
    limiter = PositionLimiter(_settings(max_positions=2))
    positions = [{"instrument": "A"}, {"instrument": "B"}]
    result = limiter.can_open(positions, "C")
    assert result["allowed"] is False
    assert any("Total" in r for r in result["reasons"])


def test_position_limiter_denied_instrument():
    from quant_platform.risk.position_limiter import PositionLimiter
    limiter = PositionLimiter(_settings(max_position_per_instrument=1))
    result = limiter.can_open([{"instrument": "X"}], "X")
    assert result["allowed"] is False


# ===== Phase 6: Performance Monitor =====

def test_performance_monitor_good():
    from quant_platform.risk.performance_monitor import PerformanceMonitor
    monitor = PerformanceMonitor(_settings())
    trades = []
    for i in range(20):
        t = MagicMock()
        t.side = "sell"
        t.quantity = 10
        t.price = 100 + i
        t.executed_at = datetime.now(timezone.utc) - timedelta(days=i)
        trades.append(t)
    result = monitor.analyze(1, trades, window_days=30)
    assert "metrics" in result
    assert isinstance(result["underperforming"], bool)


def test_performance_monitor_no_trades():
    from quant_platform.risk.performance_monitor import PerformanceMonitor
    monitor = PerformanceMonitor(_settings())
    result = monitor.analyze(1, [], window_days=30)
    assert result["underperforming"] is True
    assert "No recent trades" in result["flags"]


# ===== Phase 6: Review Agent =====

@pytest.mark.asyncio
async def test_review_agent_strategy():
    from quant_platform.agents.review_agent import ReviewAgent
    llm = MockLLM({"verdict": "adjust", "suggestions": ["Tighten SL"], "reasoning": "Drawdown high", "parameter_changes": {"stop_loss": 0.03}})
    agent = ReviewAgent(llm, _settings())
    result = await agent.review_strategy({"name": "sma"}, {"win_rate": 0.45}, [])
    assert result["verdict"] == "adjust"
    assert len(result["suggestions"]) == 1


@pytest.mark.asyncio
async def test_review_agent_fallback():
    from quant_platform.agents.review_agent import ReviewAgent
    llm = MockLLM()
    llm.generate_json = AsyncMock(side_effect=Exception("fail"))
    agent = ReviewAgent(llm, _settings())
    result = await agent.review_strategy({}, {}, [])
    assert result["verdict"] == "keep"


@pytest.mark.asyncio
async def test_review_agent_batch():
    from quant_platform.agents.review_agent import ReviewAgent
    llm = MockLLM({"verdict": "keep", "suggestions": [], "reasoning": "Fine", "parameter_changes": {}})
    agent = ReviewAgent(llm, _settings())
    results = await agent.review_all([
        {"strategy": {}, "performance": {}, "recent_trades": []},
        {"strategy": {}, "performance": {}, "recent_trades": []},
    ])
    assert len(results) == 2


# ===== Phase 6: Auto Adjuster =====

def test_auto_adjuster_apply():
    from quant_platform.risk.auto_adjuster import AutoAdjuster
    adj = AutoAdjuster()
    result = adj.adjust(
        1,
        {"verdict": "adjust", "parameter_changes": {"threshold": 0.05}},
        {"stop_loss": 0.04, "position_size": 0.02, "threshold": 0.1},
    )
    assert result["strategy_id"] == 1
    assert len(result["changes_applied"]) > 0
    assert result["adjusted_params"]["stop_loss"] < 0.04
    assert result["adjusted_params"]["position_size"] < 0.02


def test_auto_adjuster_keep():
    from quant_platform.risk.auto_adjuster import AutoAdjuster
    adj = AutoAdjuster()
    result = adj.adjust(1, {"verdict": "keep"}, {"stop_loss": 0.04})
    assert result["changes_applied"] == []
    assert result["adjusted_params"]["stop_loss"] == 0.04


# ===== Phase 6: Strategy Rotator =====

def test_rotator_demote_bad():
    from quant_platform.risk.rotation import StrategyRotator
    rotator = StrategyRotator(_settings())
    strategies = [{"id": 1, "name": "bad"}, {"id": 2, "name": "good"}]
    perf = {
        1: {"metrics": {"win_rate": 0.2, "sharpe": -1.0, "max_drawdown": 0.3}},
        2: {"metrics": {"win_rate": 0.65, "sharpe": 1.5, "max_drawdown": 0.05}},
    }
    result = rotator.rotate(strategies, perf)
    assert 1 in result["demoted"]
    assert 2 in result["kept"]


def test_rotator_to_research():
    from quant_platform.risk.rotation import StrategyRotator
    rotator = StrategyRotator(_settings())
    strategies = [{"id": 3, "name": "mediocre"}]
    perf = {3: {"metrics": {"win_rate": 0.42, "sharpe": 0.3, "max_drawdown": 0.08}}}
    result = rotator.rotate(strategies, perf)
    assert 3 in result["to_research"]


# ===== Phase 6: Review Transparency Log =====

def test_review_log_operations():
    from quant_platform.risk.review_log import ReviewTransparencyLog
    log = ReviewTransparencyLog()
    log.log_review(1, "low win rate", "adjust", {"sl": "tightened"}, {"sl": 0.05}, {"sl": 0.045})
    log.log_review(2, "high dd", "demote", {}, {}, {})
    log.log_review(1, "still low", "demote", {}, {}, {})

    assert len(log.get_log()) == 3
    assert len(log.get_log(strategy_id=1)) == 2
    assert len(log.get_log(limit=1)) == 1
    log.clear()
    assert len(log.get_log()) == 0


# ===== API Endpoint Tests =====

@pytest.mark.asyncio
async def test_api_agent_activity_feed():
    from httpx import AsyncClient, ASGITransport
    from quant_platform.api.app import app
    from quant_platform.agents.activity_feed import activity_feed as af
    af.clear()
    af.log("test_agent", "test_action", {"key": "val"})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/agents/activity-feed?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

        resp2 = await ac.get("/agents/activity-feed/test_agent?limit=10")
        assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_api_risk_review_log():
    from httpx import AsyncClient, ASGITransport
    from quant_platform.api.app import app
    from quant_platform.risk.review_log import review_log as rl
    rl.clear()
    rl.log_review(99, "test", "keep", {}, {}, {})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/risk/review-log?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1


@pytest.mark.asyncio
async def test_api_position_limits():
    from httpx import AsyncClient, ASGITransport
    from quant_platform.api.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/risk/position-limits?instrument=TEST")
        assert resp.status_code == 200
        data = resp.json()
        assert "allowed" in data
