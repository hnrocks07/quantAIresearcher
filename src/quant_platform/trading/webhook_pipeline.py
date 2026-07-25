"""Webhook-to-trade pipeline — full automated flow from signal to execution."""

from __future__ import annotations

from typing import Any

from ..agents.signal_agent import SignalAgent
from ..agents.decision_agent import DecisionAgent
from ..agents.activity_feed import AgentActivityFeed
from .executor import TradingExecutor


async def process_webhook_to_trade(
    webhook_data: dict,
    signal_agent: SignalAgent,
    decision_agent: DecisionAgent,
    executor: TradingExecutor,
    activity_feed: AgentActivityFeed,
) -> dict[str, Any]:
    trace: dict[str, Any] = {"webhook": webhook_data}

    # Step 1: Signal analysis
    signal_result = await signal_agent.analyze_signal(
        strategy_name=webhook_data.get("strategy", "unknown"),
        signal=webhook_data.get("signal", {}),
        market_context=webhook_data.get("market_context", {}),
    )
    trace["signal_analysis"] = signal_result
    activity_feed.log("signal_agent", "analyze_signal", signal_result)

    # Step 2: Decision
    portfolio_state = webhook_data.get("portfolio_state", {})
    decision = await decision_agent.decide(signal_result, portfolio_state)
    trace["decision"] = decision
    activity_feed.log("decision_agent", "decide", decision)

    # Step 3: Execute if approved
    if decision.get("approved"):
        trade_result = {
            "executed": True,
            "action": decision["final_action"],
            "size": decision["adjusted_size"],
        }
        activity_feed.log("executor", "trade_placed", trade_result)
    else:
        trade_result = {"executed": False, "reason": decision.get("reasoning", "")}
        activity_feed.log("executor", "trade_skipped", trade_result)

    trace["trade_result"] = trade_result
    return trace
