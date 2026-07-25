"""Strategy promotion/demotion manager."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import Settings
from ..models import StrategyORM, TradeORM, StrategyStatus


class PromotionManager:

    def __init__(self, settings: Settings):
        self._settings = settings

    def evaluate(self, strategy: StrategyORM, trades: list[TradeORM]) -> dict[str, Any]:
        total = len(trades)
        wins = sum(1 for t in trades if (t.price or 0) > 0 and t.side == "sell")
        win_rate = wins / total if total > 0 else 0.0

        created = strategy.created_at or datetime.now(timezone.utc)
        days_in_paper = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc if created.tzinfo is None else created.tzinfo)).days

        reasons: list[str] = []
        if total < self._settings.promotion_min_trades:
            reasons.append(f"Need {self._settings.promotion_min_trades} trades, have {total}")
        if win_rate < self._settings.promotion_win_rate:
            reasons.append(f"Win rate {win_rate:.2%} below {self._settings.promotion_win_rate:.2%}")
        if days_in_paper < self._settings.paper_trading_days_required:
            reasons.append(f"Only {days_in_paper} days in paper, need {self._settings.paper_trading_days_required}")

        return {
            "eligible": len(reasons) == 0,
            "win_rate": round(win_rate, 4),
            "trade_count": total,
            "days_in_paper": days_in_paper,
            "reasons": reasons,
        }

    def promote(self, strategy_id: int, db_session) -> bool:
        s = db_session.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
        if not s:
            return False
        s.status = StrategyStatus.PROMOTED.value
        s.updated_at = datetime.now(timezone.utc)
        db_session.flush()
        return True

    def demote(self, strategy_id: int, db_session, reason: str = "") -> bool:
        s = db_session.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
        if not s:
            return False
        s.status = StrategyStatus.DEMOTED.value
        s.updated_at = datetime.now(timezone.utc)
        db_session.flush()
        return True
