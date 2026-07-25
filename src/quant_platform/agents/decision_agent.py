"""LLM-powered trade decision agent."""

from __future__ import annotations

import json
from typing import Any

from ..plugins.llm import LLMProvider
from ..risk.manager import RiskManager
from ..config import Settings


class DecisionAgent:

    def __init__(self, llm_provider: LLMProvider, risk_manager: RiskManager, settings: Settings):
        self._llm = llm_provider
        self._risk = risk_manager
        self._settings = settings

    async def decide(self, signal_analysis: dict, portfolio_state: dict) -> dict[str, Any]:
        prompt = (
            f"Signal analysis: {json.dumps(signal_analysis)}\n"
            f"Portfolio state: {json.dumps(portfolio_state)}\n\n"
            "Decide whether to approve this trade. Respond with JSON containing:\n"
            "- approved: bool\n"
            '- final_action: "buy", "sell", or "hold"\n'
            "- adjusted_size: float\n"
            "- reasoning: string\n"
            "- risk_notes: list of strings"
        )
        try:
            result = await self._llm.generate_json(
                prompt,
                system="You are a risk-aware trade decision maker. Respond only with valid JSON.",
            )
            return {
                "approved": bool(result.get("approved", False)),
                "final_action": result.get("final_action", "hold"),
                "adjusted_size": float(result.get("adjusted_size", 0)),
                "reasoning": result.get("reasoning", ""),
                "risk_notes": result.get("risk_notes", []),
            }
        except Exception:
            return {
                "approved": False,
                "final_action": "hold",
                "adjusted_size": 0.0,
                "reasoning": "LLM decision failed",
                "risk_notes": ["LLM unavailable"],
            }

    async def review_portfolio(self, positions: list) -> dict[str, Any]:
        prompt = (
            f"Open positions: {json.dumps(positions)}\n\n"
            "Review all open positions and suggest which to close or reduce. "
            "Respond with JSON containing:\n"
            "- recommendations: list of objects with position_id, action (close/reduce/hold), reasoning"
        )
        try:
            result = await self._llm.generate_json(
                prompt,
                system="You are a portfolio reviewer. Respond only with valid JSON.",
            )
            return {"recommendations": result.get("recommendations", [])}
        except Exception:
            return {"recommendations": []}
