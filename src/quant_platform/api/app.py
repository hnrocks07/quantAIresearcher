"""FastAPI application — startup, shutdown, CORS, routes."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings, RunMode
from ..database import get_engine, Base, reset_engine
from ..logging import setup_logging, get_logger
from ..event_bus import event_bus
from ..kill_switch import kill_switch

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
    version="0.2.0",
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
        "version": "0.2.0",
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
