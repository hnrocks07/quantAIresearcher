"""TradingView webhook processor — accepts alerts and creates strategies."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..database import get_db
from ..models import StrategyORM, StrategyStatus


def process_webhook(
    payload: dict,
    secret: str | None = None,
    provided_secret: str | None = None,
) -> dict:
    if secret and provided_secret != secret:
        return {"status": "rejected", "reason": "invalid_secret"}

    strategy_name = payload.get("strategy_name", "unnamed_alert")
    action = payload.get("action", "").lower()
    ticker = payload.get("ticker", "")
    price = payload.get("price", 0.0)
    timeframe = payload.get("timeframe", "1D")

    if action not in ("buy", "sell"):
        return {"status": "rejected", "reason": f"invalid_action: {action}"}

    params = {
        "action": action,
        "ticker": ticker,
        "price": price,
        "timeframe": timeframe,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    with get_db() as db:
        existing = db.query(StrategyORM).filter(
            StrategyORM.name == strategy_name
        ).first()

        if existing:
            existing.parameters = json.dumps(params)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            strategy = StrategyORM(
                name=strategy_name,
                description=f"TradingView alert: {action} {ticker} at {price}",
                source="tradingview_alert",
                source_ref=f"{ticker}:{timeframe}",
                parameters=json.dumps(params),
                status=StrategyStatus.DISCOVERED.value,
            )
            db.add(strategy)

    return {"status": "accepted", "strategy": strategy_name}
