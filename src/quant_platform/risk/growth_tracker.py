"""Growth target tracker — monitors progress toward ₹1L→₹1Cr in 250 trading days."""

from __future__ import annotations

from typing import Any

from ..config import Settings


class GrowthTracker:

    def __init__(self, settings: Settings):
        self._initial = settings.growth_target_initial
        self._final = settings.growth_target_final
        self._days = settings.growth_target_trading_days
        self._target_win_rate = settings.growth_target_win_rate
        self._win_day_pct = settings.growth_target_win_day_pct
        self._loss_day_pct = settings.growth_target_loss_day_pct

    def required_daily_rate(self) -> float:
        return (self._final / self._initial) ** (1.0 / self._days) - 1

    def expected_value(self, day_number: int) -> float:
        rate = self.required_daily_rate()
        return self._initial * (1 + rate) ** day_number

    def quarterly_milestones(self) -> dict[str, dict[str, Any]]:
        q_days = {
            "Q1": 63,
            "Q2": 125,
            "Q3": 188,
            "Q4": self._days,
        }
        return {
            label: {"day": d, "expected": round(self.expected_value(d), 0)}
            for label, d in q_days.items()
        }

    def assess(
        self,
        current_capital: float,
        trading_day: int,
        trades: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        expected = self.expected_value(trading_day)
        deviation_pct = (current_capital - expected) / expected if expected > 0 else 0

        actual_win_rate = 0.0
        avg_win_pct = 0.0
        avg_loss_pct = 0.0
        actual_rr = 0.0

        if trades:
            wins = [t for t in trades if t.get("pnl", 0) > 0]
            losses = [t for t in trades if t.get("pnl", 0) < 0]
            total = len(wins) + len(losses)
            actual_win_rate = len(wins) / total if total > 0 else 0

            if wins:
                avg_win_pct = sum(t.get("pnl_pct", 0) for t in wins) / len(wins)
            if losses:
                avg_loss_pct = abs(sum(t.get("pnl_pct", 0) for t in losses) / len(losses))
            if avg_loss_pct > 0:
                actual_rr = avg_win_pct / avg_loss_pct

        if deviation_pct >= 0.05:
            status = "ahead"
        elif deviation_pct >= -0.05:
            status = "on_track"
        elif deviation_pct >= -0.15:
            status = "behind"
        else:
            status = "critical"

        remaining_days = max(1, self._days - trading_day)
        new_daily_rate = (self._final / max(current_capital, 1)) ** (1.0 / remaining_days) - 1
        target_at_risk = new_daily_rate > 0.03

        adjustments = []
        if status == "behind":
            adjustments = [
                "increase_position_size_10pct",
                "widen_take_profit_5pct",
                "tighten_stop_loss",
                "prioritize_high_conviction",
            ]
        elif status == "critical":
            adjustments = [
                "max_position_size",
                "rotate_bottom_30pct",
                "emergency_research_scan",
                "widen_take_profit_15pct",
                "reduce_loss_cap_to_1pct",
            ]
        elif status == "ahead":
            adjustments = [
                "reduce_position_size_10pct",
                "tighten_stops_for_preservation",
            ]

        return {
            "trading_day": trading_day,
            "current_capital": round(current_capital, 2),
            "expected_capital": round(expected, 2),
            "deviation_pct": round(deviation_pct, 4),
            "status": status,
            "required_daily_rate_original": round(self.required_daily_rate(), 5),
            "required_daily_rate_now": round(new_daily_rate, 5),
            "target_at_risk": target_at_risk,
            "remaining_days": remaining_days,
            "actual_win_rate": round(actual_win_rate, 4),
            "target_win_rate": self._target_win_rate,
            "actual_rr_ratio": round(actual_rr, 2),
            "target_rr_ratio": round(self._win_day_pct / self._loss_day_pct, 2),
            "avg_win_pct": round(avg_win_pct, 4),
            "avg_loss_pct": round(avg_loss_pct, 4),
            "adjustments": adjustments,
            "milestones": self.quarterly_milestones(),
        }

    def worst_case_forecast(
        self,
        current_capital: float,
        trading_day: int,
        win_rate: float,
        avg_win_pct: float,
        avg_loss_pct: float,
    ) -> dict[str, Any]:
        remaining = max(1, self._days - trading_day)
        win_days = int(remaining * win_rate)
        loss_days = remaining - win_days

        projected = current_capital
        projected *= (1 + avg_win_pct) ** win_days
        projected *= (1 - avg_loss_pct) ** loss_days

        shortfall = self._final - projected
        on_target = projected >= self._final

        min_win_rate_needed = 0.0
        if avg_win_pct > 0 and avg_loss_pct > 0:
            import math
            target_growth = math.log(self._final / max(current_capital, 1))
            log_win = math.log(1 + avg_win_pct)
            log_loss = math.log(1 - avg_loss_pct)
            if (log_win - log_loss) != 0:
                min_win_rate_needed = (target_growth / remaining - log_loss) / (log_win - log_loss)
                min_win_rate_needed = max(0, min(1, min_win_rate_needed))

        return {
            "current_capital": round(current_capital, 2),
            "trading_day": trading_day,
            "remaining_days": remaining,
            "projected_final": round(projected, 2),
            "target_final": self._final,
            "shortfall": round(max(0, shortfall), 2),
            "on_target": on_target,
            "min_win_rate_needed": round(min_win_rate_needed, 4),
            "assumptions": {
                "win_rate": round(win_rate, 4),
                "avg_win_pct": round(avg_win_pct, 4),
                "avg_loss_pct": round(avg_loss_pct, 4),
            },
        }
