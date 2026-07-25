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
