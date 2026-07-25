"""Fee-aware strategy scoring — ranks strategies by NET profit after all costs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import StrategyORM, BacktestResultORM
from ..database import get_db
from ..logging import get_logger

logger = get_logger("scoring")


@dataclass
class StrategyScore:
    strategy_id: int
    name: str
    composite_score: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    net_profit: float = 0.0
    max_drawdown: float = 0.0
    total_fees: float = 0.0
    fee_drag_pct: float = 0.0
    is_fee_profitable: bool = False
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "composite_score": round(self.composite_score, 4),
            "win_rate": round(self.win_rate, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "profit_factor": round(self.profit_factor, 4),
            "net_profit": round(self.net_profit, 2),
            "max_drawdown": round(self.max_drawdown, 4),
            "total_fees": round(self.total_fees, 2),
            "fee_drag_pct": round(self.fee_drag_pct, 4),
            "is_fee_profitable": self.is_fee_profitable,
            "rank": self.rank,
        }


SCORE_WEIGHTS = {
    "win_rate": 0.25,
    "sharpe_ratio": 0.25,
    "profit_factor": 0.20,
    "net_profit_norm": 0.15,
    "drawdown_inv": 0.15,
}

PROMOTION_THRESHOLD = 0.80


def score_strategy(strategy_id: int) -> StrategyScore | None:
    with get_db() as db:
        strategy = db.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
        if not strategy:
            return None

        backtests = db.query(BacktestResultORM).filter(
            BacktestResultORM.strategy_id == strategy_id
        ).all()

        if not backtests:
            return StrategyScore(strategy_id=strategy_id, name=strategy.name)

        total_trades = sum(b.total_trades or 0 for b in backtests)
        winning = sum(b.winning_trades or 0 for b in backtests)
        win_rate = winning / max(total_trades, 1)

        sharpe_vals = [b.sharpe_ratio for b in backtests if b.sharpe_ratio is not None]
        avg_sharpe = sum(sharpe_vals) / len(sharpe_vals) if sharpe_vals else 0.0

        pf_vals = [b.profit_factor for b in backtests if b.profit_factor is not None]
        avg_pf = sum(pf_vals) / len(pf_vals) if pf_vals else 0.0

        net_profit = sum(b.net_profit or 0 for b in backtests)
        total_fees = sum(b.total_fees or 0 for b in backtests)
        gross_profit = sum(b.gross_profit or 0 for b in backtests)

        dd_vals = [b.max_drawdown for b in backtests if b.max_drawdown is not None]
        max_dd = max(dd_vals) if dd_vals else 0.0

        fee_drag = total_fees / gross_profit if gross_profit > 0 else 1.0

        sharpe_norm = min(max(avg_sharpe / 3.0, 0), 1.0)
        pf_norm = min(max((avg_pf - 1.0) / 2.0, 0), 1.0)
        profit_norm = min(max(net_profit / 100000, -1), 1.0)
        dd_inv = max(1.0 - max_dd, 0)

        composite = (
            SCORE_WEIGHTS["win_rate"] * win_rate
            + SCORE_WEIGHTS["sharpe_ratio"] * sharpe_norm
            + SCORE_WEIGHTS["profit_factor"] * pf_norm
            + SCORE_WEIGHTS["net_profit_norm"] * max(profit_norm, 0)
            + SCORE_WEIGHTS["drawdown_inv"] * dd_inv
        )

        score = StrategyScore(
            strategy_id=strategy_id,
            name=strategy.name,
            composite_score=composite,
            win_rate=win_rate,
            sharpe_ratio=avg_sharpe,
            profit_factor=avg_pf,
            net_profit=net_profit,
            max_drawdown=max_dd,
            total_fees=total_fees,
            fee_drag_pct=fee_drag,
            is_fee_profitable=net_profit > 0,
        )

        strategy.win_rate = win_rate
        strategy.sharpe_ratio = avg_sharpe
        strategy.max_drawdown = max_dd
        strategy.profit_factor = avg_pf
        strategy.net_profit_after_fees = net_profit

        if win_rate >= PROMOTION_THRESHOLD and net_profit > 0 and strategy.status == "scored":
            strategy.status = "shortlisted"
            logger.info(f"Strategy {strategy.name} shortlisted (win_rate={win_rate:.2%})")

        db.flush()
        return score


def rank_strategies(strategy_ids: list[int] | None = None) -> list[StrategyScore]:
    with get_db() as db:
        if strategy_ids:
            strategies = db.query(StrategyORM).filter(StrategyORM.id.in_(strategy_ids)).all()
        else:
            strategies = db.query(StrategyORM).all()

    scores = []
    for s in strategies:
        score = score_strategy(s.id)
        if score:
            scores.append(score)

    scores.sort(key=lambda x: x.composite_score, reverse=True)
    for i, s in enumerate(scores):
        s.rank = i + 1

    return scores
