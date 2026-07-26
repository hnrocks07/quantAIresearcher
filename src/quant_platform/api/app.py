"""FastAPI application — startup, shutdown, CORS, routes."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings, RunMode
from ..database import get_engine, get_db, Base, reset_engine
from ..logging import setup_logging, get_logger
from ..event_bus import event_bus
from ..kill_switch import kill_switch
from ..models import (
    AssetORM, OHLCVORM, StrategyORM, BacktestResultORM,
    PortfolioORM, PositionORM, TradeORM,
)
from ..market_profiles import list_profiles, load_profile
from ..data.ingestion import ingestion_service
from ..data.scoring import score_strategy, rank_strategies
from ..research import research_engine, activity_log, get_lineage, get_evolution_tree
from ..research.tradingview_webhook import process_webhook
from ..trading import trading_executor, PaperBroker, AngelBroker
from ..trading.decision_log import trade_decision_log
from ..research.tradingview_source import TradingViewSource
from ..risk import (
    risk_manager, DailyLossMonitor, PositionLimiter, PerformanceMonitor,
    AutoAdjuster, StrategyRotator, review_log,
)
from ..agents.activity_feed import activity_feed as agent_activity_feed
from ..trading.promotion import PromotionManager

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting quant platform in {settings.run_mode.value} mode")

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    # Wire up plugin registry with default adapters
    from ..plugins.registry import registry
    from ..trading.paper_broker import PaperBroker
    from ..llm_adapters import ClaudeAdapter, OllamaAdapter
    from ..data.yfinance_provider import YFinanceProvider
    from ..data.nse_provider import NSEProvider
    from ..data.crypto_provider import CryptoProvider
    from ..data.indstocks_provider import INDstocksProvider
    from ..data.nsedata_provider import NSEDataProvider
    try:
        from ..data.jugaad_provider import JugaadNSEProvider
    except ImportError:
        JugaadNSEProvider = None
    registry.register_broker("paper", PaperBroker)
    registry.register_broker("angel", AngelBroker)
    registry.register_research("tradingview", TradingViewSource)
    registry.register_llm("claude", ClaudeAdapter)
    registry.register_llm("ollama", OllamaAdapter)
    registry.register_data_provider("yfinance", YFinanceProvider)
    registry.register_data_provider("nse_bhav", NSEProvider)
    registry.register_data_provider("crypto", CryptoProvider)
    registry.register_data_provider("indstocks", INDstocksProvider)
    registry.register_data_provider("nsedata", NSEDataProvider)
    if JugaadNSEProvider is not None:
        registry.register_data_provider("jugaad_nse", JugaadNSEProvider)

    # Seed fee structure on startup
    from ..data.fee_sync import fee_sync
    fee_sync.seed()

    await event_bus.emit("system.startup", "api", mode=settings.run_mode.value)

    yield

    await event_bus.emit("system.shutdown", "api")
    reset_engine()
    logger.info("Quant platform shutdown complete")


app = FastAPI(
    title="Quant Platform",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "version": "0.4.0",
        "run_mode": settings.run_mode.value,
        "kill_switch": kill_switch.status(),
    }


@app.post("/kill-switch/trigger")
async def trigger_kill_switch(reason: str = "manual"):
    await kill_switch.trigger("api", reason)
    return {"status": "triggered", "reason": reason}


@app.post("/kill-switch/reset")
async def reset_kill_switch():
    await kill_switch.reset("api")
    return {"status": "reset"}


@app.get("/kill-switch/status")
async def kill_switch_status():
    return kill_switch.status()


@app.post("/kill-switch/heartbeat")
async def heartbeat():
    kill_switch.heartbeat()
    return {"status": "ok"}


@app.get("/events/recent")
async def recent_events(limit: int = 100, event_type: str | None = None):
    events = event_bus.recent(limit=limit, event_type=event_type)
    return [e.to_dict() for e in events]


@app.get("/config")
async def get_config():
    settings = get_settings()
    return {
        "run_mode": settings.run_mode.value,
        "real_trading": settings.real_trading,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "log_level": settings.log_level,
    }


# --- Data Ingestion ---

@app.post("/ingest/start")
async def start_ingestion(profile: str = "nse_equity", interval: str = "1d"):
    return await ingestion_service.start(profile, interval)


@app.get("/ingest/status")
async def ingestion_status():
    return ingestion_service.status()


@app.post("/ingest/stop")
async def stop_ingestion():
    return await ingestion_service.stop()


@app.get("/ingest/errors")
async def ingestion_errors():
    return ingestion_service.errors()


# --- Market Profiles ---

@app.get("/profiles")
async def get_profiles():
    return list_profiles()


@app.get("/profiles/{name}")
async def get_profile(name: str):
    try:
        p = load_profile(name)
        return {
            "name": p.name,
            "display_name": p.display_name,
            "currency": p.currency,
            "exchange": p.exchange,
            "data_provider": p.data_provider,
            "history_years": p.history_years,
            "instruments_count": len(p.instruments),
            "instruments_source": p.instruments_source,
            "trading_hours": p.trading_hours,
            "fee_defaults": p.fee_defaults,
        }
    except FileNotFoundError:
        return {"error": f"Profile '{name}' not found"}


# --- Assets ---

@app.get("/assets")
async def get_assets(
    exchange: str | None = None,
    asset_type: str | None = None,
    profile: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    with get_db() as db:
        q = db.query(AssetORM)
        if exchange:
            q = q.filter(AssetORM.exchange == exchange)
        if asset_type:
            q = q.filter(AssetORM.asset_type == asset_type)
        if profile:
            q = q.filter(AssetORM.market_profile == profile)
        total = q.count()
        assets = q.offset(offset).limit(limit).all()
        return {
            "total": total,
            "assets": [
                {
                    "id": a.id, "symbol": a.symbol, "name": a.name,
                    "asset_type": a.asset_type, "exchange": a.exchange,
                    "currency": a.currency, "is_active": a.is_active,
                }
                for a in assets
            ],
        }


@app.get("/assets/{asset_id}/ohlcv")
async def get_ohlcv(asset_id: int, limit: int = 500):
    with get_db() as db:
        rows = db.query(OHLCVORM).filter(
            OHLCVORM.asset_id == asset_id
        ).order_by(OHLCVORM.date.desc()).limit(limit).all()
        return [
            {
                "date": r.date.isoformat(), "open": r.open, "high": r.high,
                "low": r.low, "close": r.close, "volume": r.volume,
            }
            for r in rows
        ]


# --- Strategies ---

@app.get("/strategies")
async def get_strategies(status: str | None = None, limit: int = 50):
    with get_db() as db:
        q = db.query(StrategyORM)
        if status:
            q = q.filter(StrategyORM.status == status)
        strategies = q.order_by(StrategyORM.updated_at.desc()).limit(limit).all()
        return [
            {
                "id": s.id, "name": s.name, "status": s.status,
                "win_rate": s.win_rate, "sharpe_ratio": s.sharpe_ratio,
                "max_drawdown": s.max_drawdown, "profit_factor": s.profit_factor,
                "net_profit_after_fees": s.net_profit_after_fees,
                "is_original": s.is_original, "source": s.source,
            }
            for s in strategies
        ]


@app.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: int):
    with get_db() as db:
        s = db.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
        if not s:
            return {"error": "Not found"}
        return {
            "id": s.id, "name": s.name, "description": s.description,
            "status": s.status, "source": s.source, "version": s.version,
            "parameters": s.parameters, "win_rate": s.win_rate,
            "sharpe_ratio": s.sharpe_ratio, "max_drawdown": s.max_drawdown,
            "profit_factor": s.profit_factor,
            "net_profit_after_fees": s.net_profit_after_fees,
            "is_original": s.is_original, "is_publishable": s.is_publishable,
            "pine_script": s.pine_script,
        }


@app.post("/strategies/import")
async def import_strategy(payload: dict):
    """Manually import a strategy — Pine Script, custom params, or any trading logic."""
    import json as _json
    name = payload.get("name")
    if not name:
        return {"error": "name is required"}
    pine_script = payload.get("pine_script")
    parameters = payload.get("parameters", {})
    description = payload.get("description", f"Manually imported: {name}")
    source = payload.get("source", "manual")

    if pine_script:
        from ..research.tradingview_source import _parse_pine_to_strategy
        parsed = _parse_pine_to_strategy(name, pine_script)
        if parsed:
            parameters = {**parsed, **parameters}

    with get_db() as db:
        existing = db.query(StrategyORM).filter(StrategyORM.name == name).first()
        if existing:
            return {"error": f"Strategy '{name}' already exists", "id": existing.id}
        strategy = StrategyORM(
            name=name,
            description=description,
            source=source,
            version="1.0",
            parameters=_json.dumps(parameters),
            status="discovered",
            pine_script=pine_script,
        )
        db.add(strategy)
        db.flush()
        sid = strategy.id
    activity_log.log_action("manual_import", name, f"source={source}, has_pine={bool(pine_script)}")
    return {"status": "imported", "id": sid, "name": name, "parameters": parameters}


@app.get("/strategies/{strategy_id}/lineage")
async def strategy_lineage(strategy_id: int):
    return get_lineage(strategy_id)


@app.get("/strategies/evolution-tree")
async def evolution_tree():
    return get_evolution_tree()


@app.get("/strategies/{strategy_id}/backtests")
async def get_backtests(strategy_id: int):
    with get_db() as db:
        results = db.query(BacktestResultORM).filter(
            BacktestResultORM.strategy_id == strategy_id
        ).order_by(BacktestResultORM.created_at.desc()).all()
        return [
            {
                "id": r.id, "asset_id": r.asset_id,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "total_trades": r.total_trades, "win_rate": r.win_rate,
                "gross_profit": r.gross_profit, "total_fees": r.total_fees,
                "net_profit": r.net_profit, "sharpe_ratio": r.sharpe_ratio,
                "max_drawdown": r.max_drawdown, "profit_factor": r.profit_factor,
            }
            for r in results
        ]


# --- Scoring ---

@app.get("/scoring/rank")
async def rank_all_strategies():
    scores = rank_strategies()
    return [s.to_dict() for s in scores]


@app.get("/scoring/{strategy_id}")
async def get_strategy_score(strategy_id: int):
    score = score_strategy(strategy_id)
    if not score:
        return {"error": "Strategy not found"}
    return score.to_dict()


# --- Portfolios ---

@app.get("/portfolios")
async def get_portfolios():
    with get_db() as db:
        portfolios = db.query(PortfolioORM).all()
        return [
            {
                "id": p.id, "name": p.name, "initial_capital": p.initial_capital,
                "currency": p.currency, "is_active": p.is_active,
            }
            for p in portfolios
        ]


@app.get("/portfolios/{portfolio_id}/positions")
async def get_positions(portfolio_id: int, status: str = "open"):
    with get_db() as db:
        q = db.query(PositionORM).filter(PositionORM.portfolio_id == portfolio_id)
        if status:
            q = q.filter(PositionORM.status == status)
        positions = q.all()
        return [
            {
                "id": p.id, "asset_id": p.asset_id, "strategy_id": p.strategy_id,
                "quantity": p.quantity, "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price, "side": p.side, "status": p.status,
            }
            for p in positions
        ]


@app.get("/portfolios/{portfolio_id}/trades")
async def get_trades(portfolio_id: int, limit: int = 100):
    with get_db() as db:
        trades = db.query(TradeORM).filter(
            TradeORM.portfolio_id == portfolio_id
        ).order_by(TradeORM.executed_at.desc()).limit(limit).all()
        return [
            {
                "id": t.id, "asset_id": t.asset_id, "side": t.side,
                "quantity": t.quantity, "price": t.price,
                "commission": t.commission, "is_simulated": t.is_simulated,
                "executed_at": t.executed_at.isoformat(),
            }
            for t in trades
        ]


# --- Research Engine ---

@app.post("/research/start")
async def start_research(profile: str = "nse_equity", top_n: int = 50):
    return await research_engine.start(profile, top_n)


@app.get("/research/status")
async def research_status():
    return research_engine.status()


@app.post("/research/stop")
async def stop_research():
    return await research_engine.stop()


@app.get("/research/errors")
async def research_errors():
    return research_engine.errors()


# --- Trading Executor ---

@app.post("/trading/start")
async def start_trading(
    portfolio_name: str = "paper_trading",
    initial_capital: float = 1000000.0,
    interval: int = 60,
    broker_type: str = "paper",
):
    from ..plugins.registry import registry
    if broker_type == "paper":
        from ..data.fee_sync import fee_sync
        db_fees = fee_sync.get_fee_schedule("NSE", "equity_delivery")
        broker = PaperBroker(initial_balance=initial_capital, fee_schedule=db_fees)
    else:
        try:
            broker = registry.get_broker(broker_type)
        except KeyError:
            return {"error": f"Unknown broker: {broker_type}"}
    return await trading_executor.start(broker, portfolio_name, initial_capital, interval)


@app.get("/trading/status")
async def trading_status():
    return trading_executor.status()


@app.post("/trading/stop")
async def stop_trading():
    return await trading_executor.stop()


@app.post("/webhooks/tradingview")
async def tradingview_webhook(payload: dict):
    result = process_webhook(payload)
    return result


@app.get("/research/activity-log")
async def get_activity_log(limit: int = 100):
    return activity_log.get_log(limit)


@app.post("/research/tv-discovery/start")
async def start_tv_discovery(interval_minutes: int = 60):
    from ..research.tradingview_source import TradingViewSource
    from ..config import get_settings
    s = get_settings()
    tv = TradingViewSource(username=s.tradingview_username, password=s.tradingview_password)
    asyncio.create_task(tv.run_continuous(interval_minutes))
    return {"status": "started", "interval_minutes": interval_minutes, "authenticated": bool(s.tradingview_username)}


@app.post("/research/tv-discovery/stop")
async def stop_tv_discovery():
    from ..research.tradingview_source import TradingViewSource
    tv = TradingViewSource()
    tv.stop_continuous()
    return {"status": "stopped"}


# --- Risk Management ---

@app.get("/risk/health")
async def portfolio_health():
    return risk_manager.portfolio_health()


@app.get("/risk/correlation")
async def correlation():
    return risk_manager.correlation_matrix()


@app.get("/risk/stress-test")
async def stress_test(regime: str = "bearish"):
    return risk_manager.stress_test(regime)


@app.post("/risk/promote-demote")
async def promote_demote():
    return risk_manager.promote_or_demote()


# --- Agent Activity Feed ---

@app.get("/agents/activity-feed")
async def get_agent_activity_feed(limit: int = 100):
    return agent_activity_feed.get_feed(limit)


@app.get("/agents/activity-feed/{agent_name}")
async def get_agent_activity_by_name(agent_name: str, limit: int = 50):
    return agent_activity_feed.get_by_agent(agent_name, limit)


# --- Promotion ---

@app.post("/trading/promotion/evaluate/{strategy_id}")
async def evaluate_promotion(strategy_id: int):
    settings = get_settings()
    pm = PromotionManager(settings)
    with get_db() as db:
        s = db.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
        if not s:
            return {"error": "Strategy not found"}
        trades = db.query(TradeORM).filter(TradeORM.strategy_id == strategy_id).all()
        return pm.evaluate(s, trades)


# --- Risk Monitoring ---

@app.get("/risk/daily-loss")
async def daily_loss():
    settings = get_settings()
    from ..kill_switch import kill_switch as ks
    monitor = DailyLossMonitor(settings, ks)
    with get_db() as db:
        from datetime import datetime, timezone, timedelta
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        trades = db.query(TradeORM).filter(TradeORM.executed_at >= today_start).all()
        portfolio = db.query(PortfolioORM).first()
        capital = portfolio.initial_capital if portfolio else 1000000.0
    return await monitor.check(trades, capital)


@app.get("/risk/position-limits")
async def position_limits(instrument: str = ""):
    settings = get_settings()
    limiter = PositionLimiter(settings)
    with get_db() as db:
        positions = db.query(PositionORM).filter(PositionORM.status == "open").all()
        pos_list = [{"instrument": p.asset_id, "id": p.id} for p in positions]
    return limiter.can_open(pos_list, instrument)


@app.get("/risk/performance/{strategy_id}")
async def strategy_performance(strategy_id: int, window_days: int = 30):
    settings = get_settings()
    monitor = PerformanceMonitor(settings)
    with get_db() as db:
        trades = db.query(TradeORM).filter(TradeORM.strategy_id == strategy_id).all()
    return monitor.analyze(strategy_id, trades, window_days)


@app.get("/risk/review-log")
async def get_review_log(limit: int = 100, strategy_id: int | None = None):
    return review_log.get_log(limit, strategy_id)


@app.post("/risk/review/{strategy_id}")
async def trigger_review(strategy_id: int):
    with get_db() as db:
        s = db.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
        if not s:
            return {"error": "Strategy not found"}
        trades = db.query(TradeORM).filter(TradeORM.strategy_id == strategy_id).all()
    settings = get_settings()
    monitor = PerformanceMonitor(settings)
    perf = monitor.analyze(strategy_id, trades)
    adjuster = AutoAdjuster()
    import json as _json
    params = _json.loads(s.parameters) if s.parameters else {}
    review_result = {"verdict": "adjust" if perf["underperforming"] else "keep", "parameter_changes": {}}
    adjustment = adjuster.adjust(strategy_id, review_result, params)
    review_log.log_review(strategy_id, "; ".join(perf["flags"]), perf["recommendation"], adjustment, params, adjustment["adjusted_params"])
    return {"performance": perf, "adjustment": adjustment}


@app.post("/risk/rotate")
async def run_rotation():
    settings = get_settings()
    rotator = StrategyRotator(settings)
    monitor = PerformanceMonitor(settings)
    with get_db() as db:
        strategies = db.query(StrategyORM).filter(
            StrategyORM.status.in_(["paper_trading", "promoted", "shortlisted"])
        ).all()
        strat_list = [{"id": s.id, "name": s.name} for s in strategies]
        perf_data = {}
        for s in strategies:
            trades = db.query(TradeORM).filter(TradeORM.strategy_id == s.id).all()
            perf_data[s.id] = monitor.analyze(s.id, trades)
    return rotator.rotate(strat_list, perf_data)


# --- Growth Target Tracking ---

@app.get("/growth/status")
async def growth_status(portfolio_id: int | None = None):
    settings = get_settings()
    if not settings.growth_target_enabled:
        return {"enabled": False}
    from ..risk.growth_tracker import GrowthTracker
    tracker = GrowthTracker(settings)
    with get_db() as db:
        portfolio = db.query(PortfolioORM).first() if not portfolio_id else db.query(PortfolioORM).filter(PortfolioORM.id == portfolio_id).first()
        if not portfolio:
            return {"error": "No portfolio found"}
        capital = portfolio.initial_capital
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        created = portfolio.created_at.replace(tzinfo=timezone.utc) if portfolio.created_at and portfolio.created_at.tzinfo is None else (portfolio.created_at or now)
        trading_day = int((now - created).days * 5 / 7)
        trades = db.query(TradeORM).filter(TradeORM.portfolio_id == portfolio.id).all()
        trade_data = []
        for t in trades:
            pnl = t.quantity * t.price * (1 if t.side == "sell" else -1)
            trade_data.append({"pnl": pnl, "pnl_pct": pnl / max(capital, 1)})
    return tracker.assess(capital, trading_day, trade_data)


@app.get("/growth/forecast")
async def growth_forecast(portfolio_id: int | None = None):
    settings = get_settings()
    if not settings.growth_target_enabled:
        return {"enabled": False}
    from ..risk.growth_tracker import GrowthTracker
    tracker = GrowthTracker(settings)
    with get_db() as db:
        portfolio = db.query(PortfolioORM).first() if not portfolio_id else db.query(PortfolioORM).filter(PortfolioORM.id == portfolio_id).first()
        if not portfolio:
            return {"error": "No portfolio found"}
        capital = portfolio.initial_capital
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        created = portfolio.created_at.replace(tzinfo=timezone.utc) if portfolio.created_at and portfolio.created_at.tzinfo is None else (portfolio.created_at or now)
        trading_day = int((now - created).days * 5 / 7)
        trades = db.query(TradeORM).filter(TradeORM.portfolio_id == portfolio.id).all()
        wins = [t for t in trades if t.side == "sell" and t.quantity * t.price > 0]
        losses = [t for t in trades if t.side == "sell" and t.quantity * t.price <= 0]
        total = len(wins) + len(losses)
        wr = len(wins) / total if total > 0 else settings.growth_target_win_rate
        avg_w = settings.growth_target_win_day_pct
        avg_l = settings.growth_target_loss_day_pct
    return tracker.worst_case_forecast(capital, trading_day, wr, avg_w, avg_l)


@app.get("/positions/live")
async def live_positions():
    """All open positions with live price, gross/net P&L, and fee breakdown."""
    if not trading_executor._broker:
        return {"error": "Trading not started"}
    broker = trading_executor._broker
    fee_schedule = broker.fee_schedule()
    positions = await broker.positions()
    result = []
    # Pre-load lot sizes for all symbols
    lot_sizes = {}
    with get_db() as db:
        for pos in positions:
            sym = pos.get("symbol", "")
            if sym and sym not in lot_sizes:
                a = db.query(AssetORM).filter(AssetORM.symbol == sym).first()
                lot_sizes[sym] = (a.lot_size or 1) if a else 1

    for pos in positions:
        if pos.get("qty", 0) <= 0:
            continue
        symbol = pos.get("symbol", "")
        qty = pos["qty"]
        lot_size = lot_sizes.get(symbol, 1)
        entry_price = pos.get("avg_price", pos.get("entry_price", 0))
        quote = await broker.quote(symbol)
        current_price = quote.get("last", entry_price)
        buy_value = entry_price * qty
        sell_value = current_price * qty
        buy_fees = fee_schedule.calculate_total_fees(buy_value, "buy")
        sell_fees = fee_schedule.calculate_total_fees(sell_value, "sell")
        total_fees = buy_fees + sell_fees
        gross_pnl = sell_value - buy_value
        net_pnl = gross_pnl - total_fees
        gross_pct = gross_pnl / buy_value if buy_value > 0 else 0
        net_pct = net_pnl / buy_value if buy_value > 0 else 0
        result.append({
            "symbol": symbol,
            "qty": qty,
            "entry_price": round(entry_price, 2),
            "current_price": round(current_price, 2),
            "buy_value": round(buy_value, 2),
            "sell_value": round(sell_value, 2),
            "gross_pnl": round(gross_pnl, 2),
            "gross_pct": round(gross_pct * 100, 2),
            "total_fees": round(total_fees, 2),
            "buy_fees": round(buy_fees, 2),
            "sell_fees": round(sell_fees, 2),
            "net_pnl": round(net_pnl, 2),
            "net_pct": round(net_pct * 100, 2),
            "lot_size": lot_size,
            "is_fno": lot_size > 1,
        })
    return {"positions": result, "count": len(result)}


@app.post("/positions/book-profit")
async def book_profit(payload: dict):
    """Manually book profit — sell by symbol, qty or percentage."""
    if not trading_executor._broker:
        return {"error": "Trading not started"}
    symbol = payload.get("symbol")
    if not symbol:
        return {"error": "symbol is required"}
    sell_pct = payload.get("sell_pct")
    sell_qty = payload.get("sell_qty")
    if not sell_pct and not sell_qty:
        return {"error": "Provide sell_pct (0-100) or sell_qty"}

    broker = trading_executor._broker
    fee_schedule = broker.fee_schedule()
    positions = await broker.positions()

    target_pos = None
    for pos in positions:
        if pos.get("symbol") == symbol and pos.get("qty", 0) > 0:
            target_pos = pos
            break
    if not target_pos:
        return {"error": f"No open position for {symbol}"}

    qty = target_pos["qty"]
    entry_price = target_pos.get("avg_price", target_pos.get("entry_price", 0))
    quote = await broker.quote(symbol)
    price = quote.get("last", entry_price)

    # Look up lot size from DB for F&O instruments
    lot_size = 1
    with get_db() as db:
        asset_row = db.query(AssetORM).filter(AssetORM.symbol == symbol).first()
        if asset_row:
            lot_size = asset_row.lot_size or 1

    from ..utils import snap_to_lot
    if sell_pct:
        raw_qty = int(qty * float(sell_pct) / 100)
        actual_qty = snap_to_lot(raw_qty, lot_size)
    else:
        actual_qty = snap_to_lot(int(sell_qty), lot_size)
    actual_qty = min(actual_qty, qty)

    if actual_qty <= 0:
        return {"error": f"Calculated sell quantity is 0 (lot_size={lot_size})"}

    buy_value = entry_price * actual_qty
    sell_value = price * actual_qty
    buy_fees = fee_schedule.calculate_total_fees(buy_value, "buy")
    sell_fees = fee_schedule.calculate_total_fees(sell_value, "sell")
    total_fees = buy_fees + sell_fees
    gross_pnl = sell_value - buy_value
    net_pnl = gross_pnl - total_fees

    from ..utils import retry_async
    result = await retry_async(
        broker.place_order,
        symbol=symbol, side="sell", qty=float(actual_qty),
        order_type="market", price=price,
        max_retries=3, base_delay=1.0, label=f"manual_book_{symbol}",
    )

    if result.status == "filled":
        agent_activity_feed.log("manual_book_profit", "executed", {
            "symbol": symbol, "qty": actual_qty, "price": round(price, 2),
            "entry_price": round(entry_price, 2),
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "total_fees": round(total_fees, 2),
            "remaining_qty": qty - actual_qty,
        }, reasoning=f"Manual profit booking: {symbol} x{actual_qty} @ {price:.2f}")

        with get_db() as db:
            trade = TradeORM(
                portfolio_id=trading_executor._portfolio_id,
                asset_id=0,
                strategy_id=0,
                side="sell",
                quantity=actual_qty,
                price=price,
                commission=round(sell_fees, 2),
                order_type="market",
                is_simulated=True,
                notes=f"manual_book_profit|order_id={result.order_id}",
            )
            db.add(trade)
            db.flush()

        return {
            "status": "booked",
            "symbol": symbol,
            "qty_sold": actual_qty,
            "remaining_qty": qty - actual_qty,
            "sell_price": round(price, 2),
            "entry_price": round(entry_price, 2),
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "total_fees": round(total_fees, 2),
            "fee_breakdown": {
                "buy_fees": round(buy_fees, 2),
                "sell_fees": round(sell_fees, 2),
            },
        }

    return {"error": f"Order not filled: {result.status}", "message": result.message}


@app.get("/fees/current")
async def get_current_fees():
    """All fee structures across exchanges and segments."""
    from ..data.fee_sync import fee_sync
    return {"fees": fee_sync.get_all_fees()}


@app.get("/fees/roundtrip")
async def fee_roundtrip(exchange: str = "NSE", segment: str = "equity_delivery", trade_value: float = 100000):
    """Calculate exact round-trip fees for a given trade value."""
    from ..data.fee_sync import fee_sync
    return fee_sync.calculate_roundtrip(exchange, segment, trade_value)


@app.post("/fees/update")
async def update_fee(payload: dict):
    """Update fee rates for an exchange/segment. Send exchange, segment, and changed fields."""
    from ..data.fee_sync import fee_sync
    exchange = payload.pop("exchange", "")
    segment = payload.pop("segment", "equity_delivery")
    if not exchange:
        return {"error": "exchange is required"}
    return fee_sync.update_fee(exchange, segment, payload)


@app.post("/fees/seed")
async def reseed_fees():
    """Re-seed fee database with latest known rates."""
    from ..data.fee_sync import fee_sync
    return fee_sync.seed()


@app.post("/contracts/sync")
async def sync_contracts(profile: str | None = None):
    """Refresh lot sizes, expiry dates, contract metadata from exchange."""
    from ..data.contract_sync import contract_sync
    return await contract_sync.sync(profile)


@app.get("/contracts/status")
async def contract_sync_status():
    from ..data.contract_sync import contract_sync
    return contract_sync.status()


@app.get("/growth/milestones")
async def growth_milestones():
    settings = get_settings()
    if not settings.growth_target_enabled:
        return {"enabled": False}
    from ..risk.growth_tracker import GrowthTracker
    tracker = GrowthTracker(settings)
    return {
        "milestones": tracker.quarterly_milestones(),
        "required_daily_rate": round(tracker.required_daily_rate(), 5),
        "initial": settings.growth_target_initial,
        "target": settings.growth_target_final,
        "trading_days": settings.growth_target_trading_days,
    }
