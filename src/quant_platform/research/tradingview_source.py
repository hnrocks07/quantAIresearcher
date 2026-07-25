"""TradingView research source — auto-discovers community strategies and pulls signals."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from ..plugins.research import ResearchSource, ImportedStrategy
from ..database import get_db
from ..models import StrategyORM

logger = logging.getLogger("tradingview_source")

_TV_AVAILABLE = True
try:
    from tradingview_ta import TA_Handler, Interval
except ImportError:
    _TV_AVAILABLE = False
    logger.warning("tradingview_ta not installed")

TRADINGVIEW_COMMUNITY_URL = "https://www.tradingview.com/scripts/trending/"
TRADINGVIEW_SCRIPT_API = "https://pine-facade.tradingview.com/pine-facade/list/"
TRADINGVIEW_SCRIPT_DETAIL = "https://pine-facade.tradingview.com/pine-facade/get/"

NSE_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "KOTAKBANK", "ITC",
    "LT", "AXISBANK", "BAJFINANCE", "MARUTI", "WIPRO",
    "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "TATAMOTORS",
    "POWERGRID", "ONGC", "NTPC", "ADANIENT", "ADANIPORTS",
    "BAJAJFINSV", "HCLTECH", "TATASTEEL", "COALINDIA", "TECHM",
    "DRREDDY", "BPCL", "DIVISLAB", "HEROMOTOCO", "CIPLA",
    "GRASIM", "EICHERMOT", "APOLLOHOSP", "TATACONSUM", "HINDALCO",
    "JSWSTEEL", "UPL", "SBILIFE", "BRITANNIA", "INDUSINDBK",
    "ASIANPAINT", "M&M", "HDFCLIFE", "BAJAJ-AUTO", "DABUR",
]

INTERVALS = {
    "5m": Interval.INTERVAL_5_MINUTES if _TV_AVAILABLE else None,
    "15m": Interval.INTERVAL_15_MINUTES if _TV_AVAILABLE else None,
    "1h": Interval.INTERVAL_1_HOUR if _TV_AVAILABLE else None,
    "4h": Interval.INTERVAL_4_HOURS if _TV_AVAILABLE else None,
    "1d": Interval.INTERVAL_1_DAY if _TV_AVAILABLE else None,
    "1w": Interval.INTERVAL_1_WEEK if _TV_AVAILABLE else None,
}


def _parse_pine_to_strategy(script_name: str, pine_source: str) -> dict | None:
    """Extract strategy logic from Pine Script source into parameter dict."""
    params = {"pine_source": pine_source, "origin": "tradingview_community"}

    sma_match = re.findall(r"ta\.sma\([^,]+,\s*(\d+)\)", pine_source)
    if sma_match:
        params["type"] = "sma_crossover"
        periods = [int(x) for x in sma_match]
        if len(periods) >= 2:
            params["fast_period"] = min(periods)
            params["slow_period"] = max(periods)
        else:
            params["period"] = periods[0]

    ema_match = re.findall(r"ta\.ema\([^,]+,\s*(\d+)\)", pine_source)
    if ema_match:
        params["type"] = params.get("type", "ema_crossover")
        periods = [int(x) for x in ema_match]
        params["ema_periods"] = periods

    rsi_match = re.search(r"ta\.rsi\([^,]+,\s*(\d+)\)", pine_source)
    if rsi_match:
        params["type"] = params.get("type", "rsi")
        params["rsi_period"] = int(rsi_match.group(1))

    rsi_ob = re.search(r"(?:overbought|ob)\s*=\s*(\d+)", pine_source, re.IGNORECASE)
    rsi_os = re.search(r"(?:oversold|os)\s*=\s*(\d+)", pine_source, re.IGNORECASE)
    if rsi_ob:
        params["overbought"] = int(rsi_ob.group(1))
    if rsi_os:
        params["oversold"] = int(rsi_os.group(1))

    macd_match = re.search(r"ta\.macd\([^,]+,\s*(\d+),\s*(\d+),\s*(\d+)\)", pine_source)
    if macd_match:
        params["type"] = params.get("type", "macd")
        params["fast"] = int(macd_match.group(1))
        params["slow"] = int(macd_match.group(2))
        params["signal"] = int(macd_match.group(3))

    bb_match = re.search(r"ta\.bb\([^,]+,\s*(\d+),\s*([\d.]+)\)", pine_source)
    if bb_match:
        params["type"] = params.get("type", "bollinger")
        params["bb_period"] = int(bb_match.group(1))
        params["bb_mult"] = float(bb_match.group(2))

    atr_match = re.search(r"ta\.atr\((\d+)\)", pine_source)
    if atr_match:
        params["atr_period"] = int(atr_match.group(1))

    sl_match = re.search(r"(?:stop_?loss|sl)\s*=\s*([\d.]+)", pine_source, re.IGNORECASE)
    tp_match = re.search(r"(?:take_?profit|tp)\s*=\s*([\d.]+)", pine_source, re.IGNORECASE)
    if sl_match:
        params["stop_loss"] = float(sl_match.group(1))
    if tp_match:
        params["take_profit"] = float(tp_match.group(1))

    if "type" not in params:
        return None

    return params


TV_LOGIN_URL = "https://www.tradingview.com/accounts/signin/"
TV_SEARCH_SCRIPTS_URL = "https://www.tradingview.com/pubscripts-suggest-json/"


class TradingViewSource(ResearchSource):

    def __init__(self, username: str | None = None, password: str | None = None):
        self._client: httpx.AsyncClient | None = None
        self._discovered: list[ImportedStrategy] = []
        self._running = False
        self._username = username
        self._password = password
        self._authenticated = False

    def name(self) -> str:
        return "tradingview"

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.tradingview.com",
                "Referer": "https://www.tradingview.com/",
            },
        )
        if self._username and self._password:
            await self._login()

    async def _login(self) -> None:
        """Authenticate with TradingView to access premium scripts."""
        if not self._client:
            return
        try:
            resp = await self._client.post(
                TV_LOGIN_URL,
                data={"username": self._username, "password": self._password, "remember": "on"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code == 200 and "auth_token" in resp.text.lower():
                self._authenticated = True
                logger.info("TradingView login successful — premium scripts accessible")
            else:
                try:
                    data = resp.json()
                    if data.get("user"):
                        self._authenticated = True
                        logger.info("TradingView login successful")
                    else:
                        logger.warning(f"TradingView login failed: {data.get('error', 'unknown')}")
                except Exception:
                    logger.warning(f"TradingView login returned status {resp.status_code}")
        except Exception as e:
            logger.warning(f"TradingView login failed: {e}")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._authenticated = False

    async def discover_strategies(self, limit: int = 50) -> list[ImportedStrategy]:
        """Auto-discover strategies from TradingView: community scripts + multi-timeframe TA signals."""
        results = []

        community = await self._scrape_community_scripts(limit=limit // 2)
        results.extend(community)

        ta_strategies = await self._multi_timeframe_ta_scan(limit=limit - len(results))
        results.extend(ta_strategies)

        self._discovered = results
        return results[:limit]

    async def _scrape_community_scripts(self, limit: int = 25) -> list[ImportedStrategy]:
        """Fetch community Pine scripts — premium scripts accessible when authenticated."""
        strategies = []
        if not self._client:
            return strategies

        search_queries = ["strategy", "swing trading", "intraday", "scalping", "trend following",
                          "mean reversion", "momentum", "breakout", "RSI strategy", "MACD strategy"]

        for query in search_queries:
            if len(strategies) >= limit:
                break
            try:
                resp = await self._client.get(
                    TV_SEARCH_SCRIPTS_URL,
                    params={"search": query},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    scripts = data.get("results", data) if isinstance(data, dict) else data if isinstance(data, list) else []
                    for script in scripts:
                        if len(strategies) >= limit:
                            break
                        script_id = script.get("scriptIdPart", "") if isinstance(script, dict) else ""
                        if not script_id:
                            continue
                        detail = await self._fetch_script_detail(script_id)
                        if detail:
                            strategies.append(detail)
                        await asyncio.sleep(0.3)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Script search for '{query}' failed: {e}")

        try:
            resp = await self._client.get(
                TRADINGVIEW_SCRIPT_API,
                params={"filter": "strategy", "sort": "popular", "size": limit - len(strategies)},
            )
            if resp.status_code == 200:
                scripts = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else []
                for script in scripts:
                    if len(strategies) >= limit:
                        break
                    script_id = script.get("scriptIdPart", "")
                    if not script_id:
                        continue
                    detail = await self._fetch_script_detail(script_id)
                    if detail:
                        strategies.append(detail)
                    await asyncio.sleep(0.3)
        except Exception as e:
            logger.debug(f"Popular scripts fetch failed: {e}")

        if self._authenticated:
            logger.info(f"Authenticated session — premium scripts included in {len(strategies)} results")
        return strategies

    async def _fetch_script_detail(self, script_id: str) -> ImportedStrategy | None:
        """Fetch a single Pine script and parse its strategy logic."""
        if not script_id or not self._client:
            return None

        try:
            resp = await self._client.get(
                f"{TRADINGVIEW_SCRIPT_DETAIL}{script_id}",
                params={"version": "last"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            source = data.get("source", "")
            name = data.get("scriptName", script_id)

            params = _parse_pine_to_strategy(name, source)
            if not params:
                return None

            return ImportedStrategy(
                name=f"tv_community_{name.replace(' ', '_').lower()[:50]}",
                source="tradingview_community",
                source_ref=f"pine:{script_id}",
                description=f"TradingView community strategy: {name}",
                parameters=params,
            )
        except Exception as e:
            logger.debug(f"Failed to parse script {script_id}: {e}")
            return None

    async def _multi_timeframe_ta_scan(self, limit: int = 25) -> list[ImportedStrategy]:
        """Scan NSE symbols across multiple timeframes for strong signals."""
        if not _TV_AVAILABLE:
            logger.warning("tradingview_ta not installed, skipping TA scan")
            return []

        strategies = []
        symbols = NSE_SYMBOLS[:limit]

        for symbol in symbols:
            try:
                signals_by_tf = {}
                for tf_name, tf_interval in INTERVALS.items():
                    if tf_interval is None:
                        continue
                    handler = TA_Handler(
                        symbol=symbol, screener="india",
                        exchange="NSE", interval=tf_interval,
                    )
                    analysis = handler.get_analysis()
                    summary = analysis.summary
                    signals_by_tf[tf_name] = {
                        "recommendation": summary.get("RECOMMENDATION", "NEUTRAL"),
                        "buy": summary.get("BUY", 0),
                        "sell": summary.get("SELL", 0),
                        "neutral": summary.get("NEUTRAL", 0),
                    }
                    indicators = analysis.indicators
                    signals_by_tf[tf_name]["rsi"] = indicators.get("RSI", 50)
                    signals_by_tf[tf_name]["macd"] = indicators.get("MACD.macd", 0)
                    signals_by_tf[tf_name]["macd_signal"] = indicators.get("MACD.signal", 0)
                    signals_by_tf[tf_name]["ema20"] = indicators.get("EMA20", 0)
                    signals_by_tf[tf_name]["ema50"] = indicators.get("EMA50", 0)
                    signals_by_tf[tf_name]["sma20"] = indicators.get("SMA20", 0)
                    signals_by_tf[tf_name]["bb_upper"] = indicators.get("BB.upper", 0)
                    signals_by_tf[tf_name]["bb_lower"] = indicators.get("BB.lower", 0)
                    signals_by_tf[tf_name]["close"] = indicators.get("close", 0)

                strong_buy_count = sum(1 for tf in signals_by_tf.values() if tf["recommendation"] == "STRONG_BUY")
                strong_sell_count = sum(1 for tf in signals_by_tf.values() if tf["recommendation"] == "STRONG_SELL")
                buy_count = sum(1 for tf in signals_by_tf.values() if tf["recommendation"] in ("BUY", "STRONG_BUY"))

                if strong_buy_count >= 2 or strong_sell_count >= 2 or buy_count >= 3:
                    action = "buy" if buy_count >= 2 else "sell"
                    strength = max(strong_buy_count, strong_sell_count) / len(signals_by_tf)

                    daily = signals_by_tf.get("1d", {})
                    strategy_params = {
                        "type": "multi_tf_ta",
                        "symbol": symbol,
                        "action": action,
                        "strength": round(strength, 2),
                        "timeframes": signals_by_tf,
                        "rsi_daily": daily.get("rsi", 50),
                        "macd_daily": daily.get("macd", 0),
                        "ema20_daily": daily.get("ema20", 0),
                        "ema50_daily": daily.get("ema50", 0),
                        "close": daily.get("close", 0),
                    }

                    strategies.append(ImportedStrategy(
                        name=f"tv_mtf_{symbol}_{action}",
                        source="tradingview_ta",
                        source_ref=f"{symbol}:MTF",
                        description=f"Multi-TF {action} signal for {symbol} (strength={strength:.0%})",
                        parameters=strategy_params,
                    ))

                await asyncio.sleep(0.2)
            except Exception as e:
                logger.debug(f"TA scan failed for {symbol}: {e}")

        return strategies

    async def get_strategy_details(self, source_ref: str) -> ImportedStrategy | None:
        if source_ref.startswith("pine:"):
            return await self._fetch_script_detail(source_ref[5:])

        if not _TV_AVAILABLE:
            return None
        try:
            parts = source_ref.split(":")
            symbol = parts[0]
            interval = parts[1] if len(parts) > 1 else "1D"
            interval_map = {
                "1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
                "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
                "4h": Interval.INTERVAL_4_HOURS, "1D": Interval.INTERVAL_1_DAY,
                "1W": Interval.INTERVAL_1_WEEK, "1M": Interval.INTERVAL_1_MONTH,
                "MTF": Interval.INTERVAL_1_DAY,
            }
            handler = TA_Handler(
                symbol=symbol, screener="india", exchange="NSE",
                interval=interval_map.get(interval, Interval.INTERVAL_1_DAY),
            )
            analysis = handler.get_analysis()
            return ImportedStrategy(
                name=f"tv_{symbol}_{interval}",
                source="tradingview",
                source_ref=source_ref,
                description=f"TradingView {interval} analysis for {symbol}",
                parameters={
                    "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL"),
                    "buy": analysis.summary.get("BUY", 0),
                    "sell": analysis.summary.get("SELL", 0),
                    "neutral": analysis.summary.get("NEUTRAL", 0),
                    "oscillators": analysis.oscillators,
                    "moving_averages": analysis.moving_averages,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to get details for {source_ref}: {e}")
            return None

    async def get_alerts(self) -> list[dict[str, Any]]:
        with get_db() as db:
            strategies = db.query(StrategyORM).filter(
                StrategyORM.source.in_(["tradingview", "tradingview_community", "tradingview_ta"])
            ).all()
            return [
                {"id": s.id, "name": s.name, "status": s.status, "parameters": s.parameters}
                for s in strategies
            ]

    async def run_continuous(self, interval_minutes: int = 60) -> None:
        """Continuously discover and store new strategies from TradingView."""
        self._running = True
        logger.info(f"Starting continuous TradingView strategy discovery (every {interval_minutes}m)")

        while self._running:
            try:
                await self.connect()
                strategies = await self.discover_strategies(limit=50)

                with get_db() as db:
                    new_count = 0
                    for strat in strategies:
                        existing = db.query(StrategyORM).filter(
                            StrategyORM.name == strat.name
                        ).first()
                        if not existing:
                            orm = StrategyORM(
                                name=strat.name,
                                description=strat.description,
                                source=strat.source,
                                version="1.0",
                                parameters=json.dumps(strat.parameters) if isinstance(strat.parameters, dict) else strat.parameters,
                                status="discovered",
                            )
                            db.add(orm)
                            new_count += 1
                    db.flush()

                logger.info(f"TV discovery cycle: {len(strategies)} found, {new_count} new stored")
                await self.disconnect()
            except Exception as e:
                logger.error(f"TV discovery cycle failed: {e}")

            await asyncio.sleep(interval_minutes * 60)

    def stop_continuous(self):
        self._running = False
