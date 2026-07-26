"""INDstocks data provider — free historical intraday candles (5m/15m) up to 15 years."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from ..plugins.data_provider import DataProvider
from ..logging import get_logger
from ..utils import retry_async

logger = get_logger("indstocks_provider")

BASE_URL = "https://api.indstocks.com"

INTERVAL_MAP = {
    "1m": ("1minute", 7),
    "5m": ("5minute", 7),
    "15m": ("15minute", 7),
    "30m": ("30minute", 7),
    "1h": ("60minute", 14),
    "4h": ("240minute", 14),
    "1d": ("1day", 365),
    "1w": ("1week", 365),
}

NIFTY_50_SCRIP_CODES = {
    "RELIANCE": "NSE_2885", "TCS": "NSE_11536", "HDFCBANK": "NSE_1333",
    "INFY": "NSE_1594", "ICICIBANK": "NSE_4963", "HINDUNILVR": "NSE_1394",
    "SBIN": "NSE_3045", "BHARTIARTL": "NSE_10604", "KOTAKBANK": "NSE_1922",
    "ITC": "NSE_1660", "LT": "NSE_11483", "AXISBANK": "NSE_5900",
    "BAJFINANCE": "NSE_317", "MARUTI": "NSE_10999", "WIPRO": "NSE_3787",
    "SUNPHARMA": "NSE_3351", "TITAN": "NSE_3506", "ULTRACEMCO": "NSE_11532",
    "NESTLEIND": "NSE_17963", "TATAMOTORS": "NSE_3456",
    "POWERGRID": "NSE_14977", "ONGC": "NSE_2475", "NTPC": "NSE_11630",
    "ADANIENT": "NSE_25", "ADANIPORTS": "NSE_15083",
    "BAJAJFINSV": "NSE_16675", "HCLTECH": "NSE_7229", "TATASTEEL": "NSE_3499",
    "COALINDIA": "NSE_20374", "TECHM": "NSE_13538",
    "DRREDDY": "NSE_881", "BPCL": "NSE_526", "DIVISLAB": "NSE_10940",
    "HEROMOTOCO": "NSE_1348", "CIPLA": "NSE_694",
    "GRASIM": "NSE_1232", "EICHERMOT": "NSE_910", "APOLLOHOSP": "NSE_157",
    "TATACONSUM": "NSE_3432", "HINDALCO": "NSE_1363",
    "JSWSTEEL": "NSE_11723", "UPL": "NSE_11287", "SBILIFE": "NSE_21808",
    "BRITANNIA": "NSE_547", "INDUSINDBK": "NSE_5258",
    "ASIANPAINT": "NSE_236", "M&M": "NSE_2031", "HDFCLIFE": "NSE_467",
    "BAJAJ-AUTO": "NSE_16669", "DABUR": "NSE_772",
}


class INDstocksProvider(DataProvider):

    def __init__(self, token: str | None = None):
        self._token = token
        self._client: httpx.AsyncClient | None = None
        self._scrip_cache: dict[str, str] = dict(NIFTY_50_SCRIP_CODES)

    def name(self) -> str:
        return "indstocks"

    async def connect(self) -> None:
        if not self._token:
            from ..config import get_settings
            self._token = get_settings().indstocks_token
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
            headers={"Authorization": self._token or ""},
        )
        if self._token:
            try:
                await self._fetch_instruments_master()
            except Exception as e:
                logger.debug(f"Instruments master fetch skipped: {e}")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_instruments_master(self) -> None:
        if not self._client:
            return
        try:
            resp = await self._client.get("/market/instruments", params={"exchange": "NSE"})
            if resp.status_code == 200:
                data = resp.json()
                instruments = data.get("data", data) if isinstance(data, dict) else data
                if isinstance(instruments, list):
                    for inst in instruments:
                        symbol = inst.get("tradingSymbol", inst.get("symbol", ""))
                        scrip = inst.get("scripCode", inst.get("securityId", ""))
                        if symbol and scrip:
                            clean = symbol.replace(".NS", "").replace("-EQ", "").upper()
                            self._scrip_cache[clean] = f"NSE_{scrip}" if not str(scrip).startswith("NSE_") else str(scrip)
                    logger.info(f"Cached {len(self._scrip_cache)} scrip codes from INDstocks")
        except Exception as e:
            logger.debug(f"Instruments master error: {e}")

    def _resolve_scrip(self, symbol: str) -> str | None:
        clean = symbol.replace(".NS", "").replace("-EQ", "").upper()
        return self._scrip_cache.get(clean)

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | datetime,
        end_date: date | datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        if not self._client:
            return []

        scrip = self._resolve_scrip(symbol)
        if not scrip:
            logger.debug(f"No scrip code for {symbol}")
            return []

        api_interval, max_days = INTERVAL_MAP.get(interval, ("1day", 365))

        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_date = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            end_date = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)

        all_candles: list[dict[str, Any]] = []
        chunk_start = start_date

        while chunk_start < end_date:
            chunk_end = min(chunk_start + timedelta(days=max_days), end_date)
            start_ms = int(chunk_start.timestamp() * 1000)
            end_ms = int(chunk_end.timestamp() * 1000)

            try:
                resp = await retry_async(
                    self._client.get,
                    f"/market/historical/{api_interval}",
                    params={"scrip-codes": scrip, "start_time": start_ms, "end_time": end_ms},
                    max_retries=3, base_delay=1.0, label=f"indstocks_{symbol}",
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candles = data.get("data", {}).get("candles", [])
                    for c in candles:
                        if len(c) >= 6:
                            dt = datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc)
                            all_candles.append({
                                "date": dt,
                                "open": float(c[1]),
                                "high": float(c[2]),
                                "low": float(c[3]),
                                "close": float(c[4]),
                                "volume": float(c[5]),
                            })
                elif resp.status_code == 429:
                    logger.warning("INDstocks rate limited, waiting 5s")
                    await asyncio.sleep(5)
                    continue
            except Exception as e:
                logger.debug(f"INDstocks fetch failed for {symbol} ({chunk_start}): {e}")

            chunk_start = chunk_end
            await asyncio.sleep(0.3)

        return all_candles

    async def fetch_instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
        result = []
        for symbol in self._scrip_cache:
            result.append({
                "symbol": symbol,
                "name": symbol,
                "asset_type": "equity",
                "exchange": "NSE",
                "currency": "INR",
            })
        return result

    async def search_symbol(self, query: str) -> list[dict[str, Any]]:
        clean = query.upper().replace(".NS", "").replace("-EQ", "")
        matches = []
        for sym in self._scrip_cache:
            if clean in sym:
                matches.append({"symbol": sym, "name": sym, "asset_type": "equity", "exchange": "NSE"})
        return matches
