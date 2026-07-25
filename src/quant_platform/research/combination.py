"""Strategy combination — find best-of-best by combining winning strategies."""

from __future__ import annotations

import json
import logging
from itertools import combinations
from typing import Any

from .strategies import SignalResult

logger = logging.getLogger("combination")


def combine_strategies(
    strategy_a_signals: SignalResult,
    strategy_b_signals: SignalResult,
    mode: str = "and",
) -> SignalResult:
    n = min(len(strategy_a_signals.entries), len(strategy_b_signals.entries))
    if mode == "and":
        entries = [strategy_a_signals.entries[i] and strategy_b_signals.entries[i] for i in range(n)]
    elif mode == "or":
        entries = [strategy_a_signals.entries[i] or strategy_b_signals.entries[i] for i in range(n)]
    elif mode == "majority":
        entries = [strategy_a_signals.entries[i] and strategy_b_signals.entries[i] for i in range(n)]
    else:
        entries = [strategy_a_signals.entries[i] and strategy_b_signals.entries[i] for i in range(n)]

    exits = [strategy_a_signals.exits[i] or strategy_b_signals.exits[i] for i in range(n)]

    return SignalResult(
        entries=entries,
        exits=exits,
        name=f"{strategy_a_signals.name}+{strategy_b_signals.name}",
        parameters={"a": strategy_a_signals.parameters, "b": strategy_b_signals.parameters, "mode": mode},
    )


def combine_three(sig_a: SignalResult, sig_b: SignalResult, sig_c: SignalResult) -> SignalResult:
    """3-way majority vote — enter when 2 of 3 agree."""
    n = min(len(sig_a.entries), len(sig_b.entries), len(sig_c.entries))
    entries = [
        (int(sig_a.entries[i]) + int(sig_b.entries[i]) + int(sig_c.entries[i])) >= 2
        for i in range(n)
    ]
    exits = [sig_a.exits[i] or sig_b.exits[i] or sig_c.exits[i] for i in range(n)]
    return SignalResult(
        entries=entries, exits=exits,
        name=f"{sig_a.name}+{sig_b.name}+{sig_c.name}",
        parameters={"a": sig_a.parameters, "b": sig_b.parameters, "c": sig_c.parameters, "mode": "majority_3"},
    )


def generate_combinations(strategies: dict, max_ways: int = 2) -> list[tuple]:
    """Generate all 2-way and optionally 3-way combinations."""
    keys = list(strategies.keys())
    pairs = list(combinations(keys, 2))
    if max_ways >= 3 and len(keys) >= 3:
        triples = list(combinations(keys, 3))
        return pairs + triples
    return pairs


class BestOfBestFinder:
    """Iteratively combine winning strategies to find the best composite."""

    def __init__(self, backtest_engine, fee_schedule=None):
        self._engine = backtest_engine
        self._fee_schedule = fee_schedule
        self._results: list[dict] = []

    def find_best(
        self,
        winners: dict[str, dict],
        prices: list[float],
        dates: list,
        strategy_funcs: dict,
        top_n: int = 5,
        include_triples: bool = True,
    ) -> list[dict]:
        """
        winners: {strategy_name: {params: dict, win_rate: float, sharpe: float, ...}}
        Returns sorted list of best combinations with backtest results.
        """
        self._results = []
        winner_names = list(winners.keys())

        if len(winner_names) < 2:
            return []

        for name_a, name_b in combinations(winner_names, 2):
            self._test_pair(name_a, name_b, winners, prices, dates, strategy_funcs)

        if include_triples and len(winner_names) >= 3:
            top_pairs = sorted(self._results, key=lambda x: x["score"], reverse=True)[:top_n]
            pair_names = set()
            for p in top_pairs:
                pair_names.update(p["components"])

            for name_a, name_b, name_c in combinations(winner_names, 3):
                if name_a in pair_names or name_b in pair_names or name_c in pair_names:
                    self._test_triple(name_a, name_b, name_c, winners, prices, dates, strategy_funcs)

        self._results.sort(key=lambda x: x["score"], reverse=True)

        for combo in self._results[:top_n]:
            beats_all = all(
                combo["win_rate"] > winners.get(c, {}).get("win_rate", 0)
                for c in combo["components"]
            )
            combo["beats_all_components"] = beats_all

        return self._results[:top_n]

    def _test_pair(self, name_a, name_b, winners, prices, dates, strategy_funcs):
        func_a = strategy_funcs.get(name_a)
        func_b = strategy_funcs.get(name_b)
        if not func_a or not func_b:
            return

        try:
            params_a = winners[name_a].get("params", {})
            params_b = winners[name_b].get("params", {})
            sig_a = func_a(prices, **params_a)
            sig_b = func_b(prices, **params_b)

            for mode in ("and", "or"):
                combined = combine_strategies(sig_a, sig_b, mode=mode)
                result = self._engine.run_signal_backtest(
                    prices=prices[:len(combined.entries)],
                    dates=dates[:len(combined.entries)],
                    entries=combined.entries,
                    exits=combined.exits,
                )
                if result.total_trades > 0:
                    score = self._compute_score(result)
                    self._results.append({
                        "name": f"{name_a}+{name_b}_{mode}",
                        "components": [name_a, name_b],
                        "mode": mode,
                        "win_rate": result.win_rate,
                        "sharpe": result.sharpe_ratio,
                        "profit_factor": result.profit_factor,
                        "net_profit": result.net_profit,
                        "total_trades": result.total_trades,
                        "max_drawdown": result.max_drawdown,
                        "score": score,
                    })
        except Exception as e:
            logger.debug(f"Pair {name_a}+{name_b} failed: {e}")

    def _test_triple(self, name_a, name_b, name_c, winners, prices, dates, strategy_funcs):
        func_a = strategy_funcs.get(name_a)
        func_b = strategy_funcs.get(name_b)
        func_c = strategy_funcs.get(name_c)
        if not func_a or not func_b or not func_c:
            return

        try:
            params_a = winners[name_a].get("params", {})
            params_b = winners[name_b].get("params", {})
            params_c = winners[name_c].get("params", {})
            sig_a = func_a(prices, **params_a)
            sig_b = func_b(prices, **params_b)
            sig_c = func_c(prices, **params_c)

            combined = combine_three(sig_a, sig_b, sig_c)
            result = self._engine.run_signal_backtest(
                prices=prices[:len(combined.entries)],
                dates=dates[:len(combined.entries)],
                entries=combined.entries,
                exits=combined.exits,
            )
            if result.total_trades > 0:
                score = self._compute_score(result)
                self._results.append({
                    "name": f"{name_a}+{name_b}+{name_c}_majority",
                    "components": [name_a, name_b, name_c],
                    "mode": "majority_3",
                    "win_rate": result.win_rate,
                    "sharpe": result.sharpe_ratio,
                    "profit_factor": result.profit_factor,
                    "net_profit": result.net_profit,
                    "total_trades": result.total_trades,
                    "max_drawdown": result.max_drawdown,
                    "score": score,
                })
        except Exception as e:
            logger.debug(f"Triple {name_a}+{name_b}+{name_c} failed: {e}")

    def _compute_score(self, result) -> float:
        wr = result.win_rate * 25
        sr = min(max(result.sharpe_ratio, -2), 5) / 5 * 25
        pf = min(result.profit_factor, 5) / 5 * 20
        np_ = 15 if result.net_profit > 0 else 0
        dd = (1 - min(result.max_drawdown, 1)) * 15
        return wr + sr + pf + np_ + dd
