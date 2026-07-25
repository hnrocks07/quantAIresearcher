"""Strategy rotator — identifies underperformers for demotion or research."""

from __future__ import annotations

from typing import Any

from ..config import Settings


class StrategyRotator:

    def __init__(self, settings: Settings):
        self._settings = settings

    def rotate(self, strategies: list[dict], performance_data: dict) -> dict[str, Any]:
        demoted: list[int] = []
        to_research: list[int] = []
        kept: list[int] = []
        reasoning: dict[int, str] = {}

        for s in strategies:
            sid = s.get("id", 0)
            perf = performance_data.get(str(sid), performance_data.get(sid, {}))
            metrics = perf.get("metrics", {})

            win_rate = metrics.get("win_rate", 0)
            sharpe = metrics.get("sharpe", 0)
            max_dd = metrics.get("max_drawdown", 0)

            if win_rate < 0.3 or sharpe < -0.5:
                demoted.append(sid)
                reasoning[sid] = f"Demoted: win_rate={win_rate:.2%}, sharpe={sharpe:.2f}"
            elif win_rate < 0.45 or max_dd > 0.15:
                to_research.append(sid)
                reasoning[sid] = f"To research: win_rate={win_rate:.2%}, drawdown={max_dd:.2%}"
            else:
                kept.append(sid)
                reasoning[sid] = "Kept: performing within bounds"

        return {
            "demoted": demoted,
            "to_research": to_research,
            "kept": kept,
            "reasoning": reasoning,
        }
