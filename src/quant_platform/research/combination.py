"""Strategy combination — AND/OR logic for signal merging."""

from __future__ import annotations

from itertools import combinations
from .strategies import SignalResult


def combine_strategies(
    strategy_a_signals: SignalResult,
    strategy_b_signals: SignalResult,
) -> SignalResult:
    n = min(len(strategy_a_signals.entries), len(strategy_b_signals.entries))
    entries = [
        strategy_a_signals.entries[i] and strategy_b_signals.entries[i]
        for i in range(n)
    ]
    exits = [
        strategy_a_signals.exits[i] or strategy_b_signals.exits[i]
        for i in range(n)
    ]
    return SignalResult(
        entries=entries,
        exits=exits,
        name=f"{strategy_a_signals.name}+{strategy_b_signals.name}",
        parameters={
            "a": strategy_a_signals.parameters,
            "b": strategy_b_signals.parameters,
        },
    )


def generate_combinations(strategies: dict) -> list[tuple[str, str]]:
    return list(combinations(strategies.keys(), 2))
