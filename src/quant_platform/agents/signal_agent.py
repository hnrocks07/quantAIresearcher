"""LLM-powered signal analysis agent."""

from __future__ import annotations

import json
from typing import Any

from ..plugins.llm import LLMProvider
from ..config import Settings


class SignalAgent:

    def __init__(self, llm_provider: LLMProvider, settings: Settings):
        self._llm = llm_provider
        self._settings = settings

    async def analyze_signal(
        self, strategy_name: str, signal: dict, market_context: dict
    ) -> dict[str, Any]:
        prompt = (
            f"Strategy: {strategy_name}\n"
            f"Signal: {json.dumps(signal)}\n"
            f"Market context: {json.dumps(market_context)}\n\n"
            "Analyze this trading signal. Respond with JSON containing:\n"
            '- action: "buy", "sell", or "hold"\n'
            "- confidence: float 0-1\n"
            "- reasoning: string\n"
            "- position_size_suggestion: float 0-1"
        )
        try:
            result = await self._llm.generate_json(
                prompt,
                system="You are a quantitative trading analyst. Respond only with valid JSON.",
            )
            return {
                "action": result.get("action", "hold"),
                "confidence": float(result.get("confidence", 0)),
                "reasoning": result.get("reasoning", ""),
                "position_size_suggestion": float(result.get("position_size_suggestion", 0)),
            }
        except Exception:
            return {
                "action": "hold",
                "confidence": 0.0,
                "reasoning": "LLM analysis failed",
                "position_size_suggestion": 0.0,
            }

    async def batch_analyze(self, signals: list[dict]) -> list[dict[str, Any]]:
        results = []
        for sig in signals:
            r = await self.analyze_signal(
                sig.get("strategy_name", "unknown"),
                sig.get("signal", {}),
                sig.get("market_context", {}),
            )
            results.append(r)
        return results
