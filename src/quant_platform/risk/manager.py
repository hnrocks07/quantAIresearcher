"""Risk manager — correlation matrix, stress testing, drawdown limits, portfolio health."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from ..database import get_db
from ..models import (
    StrategyORM, BacktestResultORM, OHLCVORM, AssetORM,
    StrategyStatus,
)
from ..logging import get_logger

logger = get_logger("risk")

MAX_CORRELATION = 0.70
MAX_PORTFOLIO_DRAWDOWN = 0.20
MAX_STRATEGY_DRAWDOWN = 0.15
MIN_STRATEGIES_FOR_DIVERSIFICATION = 3


class RiskManager:

    def portfolio_health(self) -> dict[str, Any]:
        with get_db() as db:
            active = db.query(StrategyORM).filter(
                StrategyORM.status.in_([
                    StrategyStatus.SHORTLISTED.value,
                    StrategyStatus.PAPER_TRADING.value,
                    StrategyStatus.PROMOTED.value,
                ])
            ).all()

        if not active:
            return {
                "status": "no_active_strategies",
                "strategies": 0,
                "diversified": False,
                "max_drawdown": 0,
                "warnings": ["No active strategies found"],
            }

        drawdowns = [s.max_drawdown or 0 for s in active]
        max_dd = max(drawdowns) if drawdowns else 0
        avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else 0

        warnings = []
        if len(active) < MIN_STRATEGIES_FOR_DIVERSIFICATION:
            warnings.append(f"Only {len(active)} strategies active — need {MIN_STRATEGIES_FOR_DIVERSIFICATION} for diversification")
        if max_dd > MAX_STRATEGY_DRAWDOWN:
            warnings.append(f"Max drawdown {max_dd:.2%} exceeds limit {MAX_STRATEGY_DRAWDOWN:.2%}")

        breached = [s.name for s in active if (s.max_drawdown or 0) > MAX_STRATEGY_DRAWDOWN]
        if breached:
            warnings.append(f"Strategies exceeding drawdown limit: {', '.join(breached)}")

        return {
            "status": "healthy" if not warnings else "warnings",
            "strategies": len(active),
            "diversified": len(active) >= MIN_STRATEGIES_FOR_DIVERSIFICATION,
            "max_drawdown": round(max_dd, 4),
            "avg_drawdown": round(avg_dd, 4),
            "warnings": warnings,
            "strategy_summary": [
                {
                    "name": s.name,
                    "status": s.status,
                    "win_rate": s.win_rate,
                    "sharpe": s.sharpe_ratio,
                    "drawdown": s.max_drawdown,
                    "net_profit": s.net_profit_after_fees,
                }
                for s in active
            ],
        }

    def correlation_matrix(self, strategy_ids: list[int] | None = None) -> dict[str, Any]:
        with get_db() as db:
            if strategy_ids:
                strategies = db.query(StrategyORM).filter(StrategyORM.id.in_(strategy_ids)).all()
            else:
                strategies = db.query(StrategyORM).filter(
                    StrategyORM.status.in_([
                        StrategyStatus.SCORED.value,
                        StrategyStatus.SHORTLISTED.value,
                        StrategyStatus.PAPER_TRADING.value,
                    ])
                ).all()

        if len(strategies) < 2:
            return {"matrix": [], "labels": [], "highly_correlated_pairs": []}

        returns_by_strategy = {}
        for s in strategies:
            with get_db() as db:
                backtests = db.query(BacktestResultORM).filter(
                    BacktestResultORM.strategy_id == s.id
                ).all()
            if backtests:
                returns_by_strategy[s.name] = [
                    b.net_profit or 0 for b in backtests
                ]

        labels = list(returns_by_strategy.keys())
        if len(labels) < 2:
            return {"matrix": [], "labels": labels, "highly_correlated_pairs": []}

        max_len = max(len(v) for v in returns_by_strategy.values())
        matrix_data = []
        for label in labels:
            r = returns_by_strategy[label]
            padded = r + [0.0] * (max_len - len(r))
            matrix_data.append(padded)

        arr = np.array(matrix_data)
        n = len(labels)
        corr = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i == j:
                    corr[i][j] = 1.0
                else:
                    std_i = np.std(arr[i])
                    std_j = np.std(arr[j])
                    if std_i > 0 and std_j > 0:
                        corr[i][j] = float(np.corrcoef(arr[i], arr[j])[0, 1])

        highly_correlated = []
        for i in range(n):
            for j in range(i + 1, n):
                if abs(corr[i][j]) > MAX_CORRELATION:
                    highly_correlated.append({
                        "pair": [labels[i], labels[j]],
                        "correlation": round(float(corr[i][j]), 4),
                    })

        return {
            "matrix": [[round(float(c), 4) for c in row] for row in corr],
            "labels": labels,
            "highly_correlated_pairs": highly_correlated,
        }

    def stress_test(self, regime: str = "bearish") -> dict[str, Any]:
        multiplier = {"bearish": -0.3, "sideways": 0.0, "bullish": 0.3}.get(regime, 0.0)

        with get_db() as db:
            strategies = db.query(StrategyORM).filter(
                StrategyORM.status.in_([
                    StrategyStatus.SHORTLISTED.value,
                    StrategyStatus.PAPER_TRADING.value,
                ])
            ).all()

        results = []
        total_stressed_pnl = 0.0

        for s in strategies:
            net = s.net_profit_after_fees or 0
            stressed_pnl = net * (1 + multiplier)
            dd = (s.max_drawdown or 0) * (1 + abs(multiplier))
            total_stressed_pnl += stressed_pnl

            results.append({
                "name": s.name,
                "original_pnl": round(net, 2),
                "stressed_pnl": round(stressed_pnl, 2),
                "original_drawdown": round(s.max_drawdown or 0, 4),
                "stressed_drawdown": round(min(dd, 1.0), 4),
                "survives": stressed_pnl > 0 and dd < MAX_PORTFOLIO_DRAWDOWN,
            })

        survivors = sum(1 for r in results if r["survives"])

        return {
            "regime": regime,
            "multiplier": multiplier,
            "total_strategies": len(results),
            "survivors": survivors,
            "total_stressed_pnl": round(total_stressed_pnl, 2),
            "portfolio_survives": total_stressed_pnl > 0 and survivors > 0,
            "strategies": results,
        }

    def promote_or_demote(self) -> dict[str, Any]:
        promoted = []
        demoted = []

        with get_db() as db:
            paper_trading = db.query(StrategyORM).filter(
                StrategyORM.status == StrategyStatus.PAPER_TRADING.value
            ).all()

            for s in paper_trading:
                win = s.win_rate or 0
                net = s.net_profit_after_fees or 0
                dd = s.max_drawdown or 0

                if win >= 0.80 and net > 0 and dd < MAX_STRATEGY_DRAWDOWN:
                    s.status = StrategyStatus.PROMOTED.value
                    promoted.append(s.name)
                    logger.info(f"PROMOTED: {s.name} (win={win:.2%}, net={net:.2f})")
                elif win < 0.50 or net < 0 or dd > MAX_PORTFOLIO_DRAWDOWN:
                    s.status = StrategyStatus.DEMOTED.value
                    demoted.append(s.name)
                    logger.info(f"DEMOTED: {s.name} (win={win:.2%}, net={net:.2f})")

            db.flush()

        return {
            "promoted": promoted,
            "demoted": demoted,
            "total_promoted": len(promoted),
            "total_demoted": len(demoted),
        }


risk_manager = RiskManager()
