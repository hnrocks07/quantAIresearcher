"""Autonomous data ingestion service — fetches, retries, recovers on its own."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from ..database import get_db
from ..models import AssetORM, OHLCVORM
from ..market_profiles import load_profile, MarketProfile
from ..event_bus import event_bus
from ..logging import get_logger
from ..plugins.data_provider import DataProvider

logger = get_logger("ingestion")


class IngestionStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class IngestionService:

    def __init__(self, provider_name: str | None = None):
        self._status = IngestionStatus.IDLE
        self._started_at: float | None = None
        self._completed_at: float | None = None
        self._total_instruments: int = 0
        self._processed: int = 0
        self._rows_inserted: int = 0
        self._errors: list[dict[str, Any]] = []
        self._current_symbol: str = ""
        self._stop_requested: bool = False
        self._task: asyncio.Task | None = None
        self._provider_name: str | None = provider_name

    def status(self) -> dict[str, Any]:
        elapsed = 0.0
        if self._started_at:
            end = self._completed_at or time.monotonic()
            elapsed = round(end - self._started_at, 1)
        return {
            "status": self._status.value,
            "total_instruments": self._total_instruments,
            "processed": self._processed,
            "rows_inserted": self._rows_inserted,
            "errors_count": len(self._errors),
            "current_symbol": self._current_symbol,
            "elapsed_seconds": elapsed,
            "progress_pct": round(self._processed / max(self._total_instruments, 1) * 100, 1),
        }

    def errors(self) -> list[dict[str, Any]]:
        return self._errors[-100:]

    async def start(self, profile_name: str = "nse_equity") -> dict[str, str]:
        if self._status == IngestionStatus.RUNNING:
            return {"error": "Already running"}

        self._status = IngestionStatus.RUNNING
        self._started_at = time.monotonic()
        self._completed_at = None
        self._processed = 0
        self._rows_inserted = 0
        self._errors = []
        self._stop_requested = False

        self._task = asyncio.create_task(self._run(profile_name))
        return {"status": "started", "profile": profile_name}

    async def stop(self) -> dict[str, str]:
        self._stop_requested = True
        return {"status": "stop_requested"}

    def _get_provider(self, profile: MarketProfile) -> DataProvider:
        from ..plugins.registry import registry
        from ..config import get_settings

        provider_name = self._provider_name or profile.data_provider or get_settings().data_provider
        return registry.get_data_provider(provider_name)

    async def _run(self, profile_name: str) -> None:
        try:
            profile = load_profile(profile_name)
            provider = self._get_provider(profile)
            await provider.connect()

            try:
                instruments = await self._resolve_instruments(profile, provider)
                self._total_instruments = len(instruments)

                await event_bus.emit("ingestion.started", "ingestion", profile=profile_name, total=self._total_instruments)
                logger.info(f"Starting ingestion for {profile_name}: {self._total_instruments} instruments")

                for i, inst in enumerate(instruments):
                    if self._stop_requested:
                        self._status = IngestionStatus.STOPPED
                        logger.info("Ingestion stopped by request")
                        return

                    self._current_symbol = inst["symbol"]
                    try:
                        rows = await self._fetch_instrument(inst, profile, provider)
                        self._rows_inserted += rows
                    except Exception as e:
                        self._errors.append({
                            "symbol": inst["symbol"],
                            "error": str(e),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        logger.warning(f"Failed to fetch {inst['symbol']}: {e}")

                    self._processed = i + 1

                    if self._processed % 50 == 0:
                        logger.info(f"Progress: {self._processed}/{self._total_instruments} ({self._rows_inserted} rows)")

                self._status = IngestionStatus.COMPLETED
                self._completed_at = time.monotonic()
                await event_bus.emit("ingestion.completed", "ingestion",
                                    rows=self._rows_inserted, errors=len(self._errors))
                logger.info(f"Ingestion complete: {self._rows_inserted} rows, {len(self._errors)} errors")

                # AUTO-PIPELINE: trigger research after ingestion completes
                await self._auto_start_research(profile_name)
            finally:
                await provider.disconnect()

        except Exception as e:
            self._status = IngestionStatus.FAILED
            self._completed_at = time.monotonic()
            logger.error(f"Ingestion failed: {e}")
            self._errors.append({"error": str(e), "fatal": True})

    async def _auto_start_research(self, profile_name: str) -> None:
        """Auto-trigger research + TV discovery + paper trading after ingestion."""
        try:
            from ..research.engine import research_engine
            from ..config import get_settings
            settings = get_settings()
            source_mode = settings.research_source_mode

            logger.info(f"AUTO-PIPELINE: Starting research for {profile_name} (source_mode={source_mode})")
            await research_engine.start(profile_name, settings.research_top_n_assets, source_mode)

            # Start TradingView continuous discovery in background
            try:
                from ..research.tradingview_source import TradingViewSource
                tv = TradingViewSource(username=settings.tradingview_username, password=settings.tradingview_password)
                import asyncio
                asyncio.create_task(tv.run_continuous(settings.research_interval_minutes))
                logger.info("AUTO-PIPELINE: TradingView continuous discovery started")
            except Exception as e:
                logger.debug(f"TV discovery auto-start skipped: {e}")

            # Start paper trading in background
            try:
                from ..trading.executor import trading_executor
                from ..trading.paper_broker import PaperBroker
                broker = PaperBroker(initial_balance=1000000.0)
                await trading_executor.start(broker, "paper_trading", 1000000.0, 60)
                logger.info("AUTO-PIPELINE: Paper trading started")
            except Exception as e:
                logger.debug(f"Paper trading auto-start skipped: {e}")

        except Exception as e:
            logger.warning(f"Auto-pipeline start failed: {e}")

    async def _resolve_instruments(self, profile: MarketProfile, provider: DataProvider) -> list[dict[str, str]]:
        instruments = list(profile.instruments)

        if profile.instruments_source == "nifty500":
            provider_instruments = await provider.fetch_instruments(exchange=profile.exchange)
            if provider_instruments:
                instruments.extend(provider_instruments)
            else:
                nifty500 = await self._fetch_nifty500_list()
                instruments.extend(nifty500)
        elif profile.instruments_source == "nse_fno_csv":
            provider_instruments = await provider.fetch_instruments(exchange="NSE_FNO")
            if provider_instruments:
                instruments.extend(provider_instruments)
        elif profile.instruments_source == "provider":
            provider_instruments = await provider.fetch_instruments(exchange=profile.exchange)
            instruments.extend(provider_instruments)

        return instruments

    async def _fetch_nifty500_list(self) -> list[dict[str, str]]:
        try:
            import pandas as pd

            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, lambda: pd.read_csv(url))
            result = []
            for _, row in df.iterrows():
                symbol = row.get("Symbol", "")
                name = row.get("Company Name", symbol)
                if symbol:
                    entry = {
                        "symbol": f"{symbol}.NS",
                        "name": str(name),
                        "asset_type": "equity",
                    }
                    industry = row.get("Industry", "")
                    if industry:
                        entry["sector"] = str(industry)
                    result.append(entry)
            logger.info(f"Fetched NIFTY 500 list: {len(result)} stocks")
            return result
        except Exception as e:
            logger.warning(f"Could not fetch NIFTY 500 list: {e}, using fallback")
            return []

    async def _fetch_instrument(self, inst: dict[str, str], profile: MarketProfile, provider: DataProvider) -> int:
        symbol = inst["symbol"]
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=profile.history_years * 365)

        ohlcv_rows = await provider.fetch_ohlcv(symbol, start_date, end_date)

        if not ohlcv_rows:
            return 0

        with get_db() as db:
            asset = db.query(AssetORM).filter(
                AssetORM.symbol == symbol,
                AssetORM.exchange == profile.exchange,
            ).first()

            if not asset:
                asset_kwargs = {
                    "symbol": symbol,
                    "name": inst.get("name", symbol),
                    "asset_type": inst.get("asset_type", profile.asset_type),
                    "exchange": profile.exchange,
                    "market_profile": profile.name,
                    "currency": inst.get("currency", profile.currency),
                    "lot_size": inst.get("lot_size", profile.lot_size_default),
                    "tick_size": profile.tick_size_default,
                }
                if inst.get("sector"):
                    asset_kwargs["sector"] = inst["sector"]
                if inst.get("market_cap_category"):
                    asset_kwargs["market_cap_category"] = inst["market_cap_category"]
                if inst.get("expiry_date"):
                    asset_kwargs["expiry_date"] = inst["expiry_date"]
                if inst.get("strike_price"):
                    asset_kwargs["strike_price"] = inst["strike_price"]
                if inst.get("option_type"):
                    asset_kwargs["option_type"] = inst["option_type"]
                if inst.get("contract_type"):
                    asset_kwargs["contract_type"] = inst["contract_type"]

                asset = AssetORM(**asset_kwargs)
                db.add(asset)
                db.flush()

            existing_dates = set()
            existing = db.query(OHLCVORM.date).filter(OHLCVORM.asset_id == asset.id).all()
            for row in existing:
                existing_dates.add(row[0].date() if hasattr(row[0], 'date') else row[0])

            rows_added = 0
            for ohlcv in ohlcv_rows:
                dt = ohlcv["date"]
                if hasattr(dt, 'date'):
                    date_key = dt.date()
                else:
                    date_key = dt

                if date_key in existing_dates:
                    continue

                ohlcv_orm = OHLCVORM(
                    asset_id=asset.id,
                    date=dt if hasattr(dt, 'hour') else datetime.combine(dt, datetime.min.time(), tzinfo=timezone.utc),
                    open=float(ohlcv.get("open", 0)),
                    high=float(ohlcv.get("high", 0)),
                    low=float(ohlcv.get("low", 0)),
                    close=float(ohlcv.get("close", 0)),
                    adj_close=float(ohlcv.get("adj_close", ohlcv.get("close", 0))),
                    volume=float(ohlcv.get("volume", 0)),
                )
                db.add(ohlcv_orm)
                rows_added += 1

            db.flush()
            return rows_added


ingestion_service = IngestionService()
