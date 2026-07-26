"""Auto adjuster — applies parameter changes based on review verdicts."""

from __future__ import annotations

from typing import Any


class AutoAdjuster:

    def adjust(self, strategy_id: int, review_result: dict, current_params: dict) -> dict[str, Any]:
        changes: list[str] = []
        adjusted = dict(current_params)

        verdict = review_result.get("verdict", "keep")

        if verdict == "adjust":
            param_changes = review_result.get("parameter_changes", {})
            for k, v in param_changes.items():
                adjusted[k] = v
                changes.append(f"{k}: {current_params.get(k)} -> {v}")

            if "stop_loss" in adjusted:
                tightened = adjusted["stop_loss"] * 0.9
                adjusted["stop_loss"] = round(tightened, 4)
                changes.append(f"stop_loss tightened by 10% to {adjusted['stop_loss']}")

            if "position_size" in adjusted:
                reduced = adjusted["position_size"] * 0.8
                adjusted["position_size"] = round(reduced, 4)
                changes.append(f"position_size reduced by 20% to {adjusted['position_size']}")

        return {
            "strategy_id": strategy_id,
            "adjusted_params": adjusted,
            "changes_applied": changes,
        }

    def growth_adjust(self, current_params: dict, assessment: dict) -> dict[str, Any]:
        changes: list[str] = []
        adjusted = dict(current_params)
        status = assessment.get("status", "on_track")

        if status == "behind":
            if "position_size" in adjusted:
                new_ps = min(adjusted["position_size"] * 1.10, 0.05)
                changes.append(f"position_size: {adjusted['position_size']} -> {round(new_ps, 4)}")
                adjusted["position_size"] = round(new_ps, 4)
            if "take_profit" in adjusted:
                new_tp = adjusted["take_profit"] * 1.05
                changes.append(f"take_profit widened 5%: {adjusted['take_profit']} -> {round(new_tp, 4)}")
                adjusted["take_profit"] = round(new_tp, 4)
            if "stop_loss" in adjusted:
                new_sl = adjusted["stop_loss"] * 0.95
                changes.append(f"stop_loss tightened 5%: {adjusted['stop_loss']} -> {round(new_sl, 4)}")
                adjusted["stop_loss"] = round(new_sl, 4)

        elif status == "critical":
            adjusted["position_size"] = 0.05
            changes.append("position_size maxed to 5%")
            if "take_profit" in adjusted:
                new_tp = adjusted["take_profit"] * 1.15
                changes.append(f"take_profit widened 15%: -> {round(new_tp, 4)}")
                adjusted["take_profit"] = round(new_tp, 4)
            if "stop_loss" in adjusted:
                new_sl = adjusted["stop_loss"] * 0.5
                changes.append(f"stop_loss halved: -> {round(new_sl, 4)}")
                adjusted["stop_loss"] = round(new_sl, 4)

        elif status == "ahead":
            if "position_size" in adjusted:
                new_ps = adjusted["position_size"] * 0.90
                changes.append(f"position_size reduced 10%: {adjusted['position_size']} -> {round(new_ps, 4)}")
                adjusted["position_size"] = round(new_ps, 4)
            if "stop_loss" in adjusted:
                new_sl = adjusted["stop_loss"] * 0.90
                changes.append(f"stop_loss tightened for preservation: -> {round(new_sl, 4)}")
                adjusted["stop_loss"] = round(new_sl, 4)

        return {
            "adjusted_params": adjusted,
            "changes_applied": changes,
            "growth_status": status,
        }
