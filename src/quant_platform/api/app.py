"""FastAPI application — startup, shutdown, CORS, routes."""

from __future__ import annotations

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
from ..research import research_engine
from ..trading import trading_executor, PaperBroker
from ..risk import risk_manager

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting quant platform in {settings.run_mode.value} mode")

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    await event_bus.emit("system.startup", "api", mode=settings.run_mode.value)

    yield

    await event_bus.emit("system.shutdown", "api")
    reset_engine()
    logger.info("Quant platform shutdown complete")


app = FastAPI(
    title="Quant Platform",
    version="0.3.0",
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
        "version": "0.3.0",
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
async def start_ingestion(profile: str = "nse_equity"):
    return await ingestion_service.start(profile)


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
):
    broker = PaperBroker(initial_balance=initial_capital)
    return await trading_executor.start(broker, portfolio_name, initial_capital, interval)


@app.get("/trading/status")
async def trading_status():
    return trading_executor.status()


@app.post("/trading/stop")
async def stop_trading():
    return await trading_executor.stop()


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
