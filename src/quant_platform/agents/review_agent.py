"""LLM-powered strategy review agent."""

from __future__ import annotations

import json
from typing import Any

from ..plugins.llm import LLMProvider
from ..config import Settings


class ReviewAgent:

    def __init__(self, llm_provider: LLMProvider, settings: Settings):
        self._llm = llm_provider
        self._settings = settings

    async def review_strategy(
        self, strategy: dict, performance: dict, recent_trades: list
    ) -> dict[str, Any]:
        prompt = (
            f"Strategy: {json.dumps(strategy)}\n"
            f"Performance: {json.dumps(performance)}\n"
            f"Recent trades: {json.dumps(recent_trades[:20])}\n\n"
            "Review this strategy's performance and suggest improvements. "
            "Respond with JSON containing:\n"
            '- verdict: "keep", "adjust", or "demote"\n'
            "- suggestions: list of strings\n"
            "- reasoning: string\n"
            "- parameter_changes: dict of param name to new value"
        )
        try:
            result = await self._llm.generate_json(
                prompt,
                system="You are a quantitative strategy reviewer. Respond only with valid JSON.",
            )
            return {
                "verdict": result.get("verdict", "keep"),
                "suggestions": result.get("suggestions", []),
                "reasoning": result.get("reasoning", ""),
                "parameter_changes": result.get("parameter_changes", {}),
            }
        except Exception:
            return {
                "verdict": "keep",
                "suggestions": [],
                "reasoning": "LLM review failed",
                "parameter_changes": {},
            }

    async def review_all(self, strategies_with_performance: list) -> list[dict[str, Any]]:
        results = []
        for item in strategies_with_performance:
            r = await self.review_strategy(
                item.get("strategy", {}),
                item.get("performance", {}),
                item.get("recent_trades", []),
            )
            results.append(r)
        return results
