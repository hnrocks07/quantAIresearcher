"""Trade decision log — persists reasoning to DB."""

from __future__ import annotations

import json
from typing import Any

from ..database import get_db
from ..models import SystemEventORM


class TradeDecisionLog:

    def log_decision(
        self,
        signal: str,
        reasoning: str,
        action: str,
        result: str,
        strategy_id: int | None = None,
        asset_id: int | None = None,
    ) -> None:
        payload = {
            "signal": signal,
            "reasoning": reasoning,
            "action": action,
            "result": result,
            "strategy_id": strategy_id,
            "asset_id": asset_id,
        }
        with get_db() as db:
            event = SystemEventORM(
                event_type="trade_decision",
                source="decision_log",
                payload=json.dumps(payload),
            )
            db.add(event)

    def get_decisions(
        self,
        limit: int = 50,
        strategy_id: int | None = None,
    ) -> list[dict[str, Any]]:
        with get_db() as db:
            q = db.query(SystemEventORM).filter(
                SystemEventORM.event_type == "trade_decision"
            )
            rows = q.order_by(SystemEventORM.created_at.desc()).limit(limit).all()
            results = []
            for row in rows:
                data = json.loads(row.payload) if row.payload else {}
                if strategy_id and data.get("strategy_id") != strategy_id:
                    continue
                data["id"] = row.id
                data["created_at"] = row.created_at.isoformat() if row.created_at else None
                results.append(data)
            return results


trade_decision_log = TradeDecisionLog()
