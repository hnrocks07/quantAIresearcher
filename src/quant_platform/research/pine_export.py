"""Pine Script v5 export for TradingView."""

from __future__ import annotations


def export_to_pine(strategy_name: str, parameters: dict, strategy_type: str) -> str:
    generators = {
        "sma_crossover": _pine_sma,
        "rsi": _pine_rsi,
        "macd": _pine_macd,
        "bollinger": _pine_bollinger,
        "mean_reversion": _pine_mean_reversion,
    }

    gen = generators.get(strategy_type.lower(), _pine_sma)
    return gen(strategy_name, parameters)


def _pine_sma(name: str, params: dict) -> str:
    fast = params.get("fast", 20)
    slow = params.get("slow", 50)
    return f"""//@version=5
strategy("{name}", overlay=true)
fast = ta.sma(close, {fast})
slow = ta.sma(close, {slow})
plot(fast, color=color.blue)
plot(slow, color=color.red)
if ta.crossover(fast, slow)
    strategy.entry("Long", strategy.long)
if ta.crossunder(fast, slow)
    strategy.close("Long")"""


def _pine_rsi(name: str, params: dict) -> str:
    period = params.get("period", 14)
    oversold = params.get("oversold", 30)
    overbought = params.get("overbought", 70)
    return f"""//@version=5
strategy("{name}", overlay=false)
rsi_val = ta.rsi(close, {period})
plot(rsi_val)
hline({oversold})
hline({overbought})
if ta.crossover(rsi_val, {oversold})
    strategy.entry("Long", strategy.long)
if ta.crossover(rsi_val, {overbought})
    strategy.close("Long")"""


def _pine_macd(name: str, params: dict) -> str:
    fast = params.get("fast", 12)
    slow = params.get("slow", 26)
    signal = params.get("signal", 9)
    return f"""//@version=5
strategy("{name}", overlay=false)
[macdLine, signalLine, _] = ta.macd(close, {fast}, {slow}, {signal})
plot(macdLine, color=color.blue)
plot(signalLine, color=color.red)
if ta.crossover(macdLine, signalLine)
    strategy.entry("Long", strategy.long)
if ta.crossunder(macdLine, signalLine)
    strategy.close("Long")"""


def _pine_bollinger(name: str, params: dict) -> str:
    period = params.get("period", 20)
    std_dev = params.get("std_dev", 2.0)
    return f"""//@version=5
strategy("{name}", overlay=true)
[mid, upper, lower] = ta.bb(close, {period}, {std_dev})
plot(mid)
plot(upper)
plot(lower)
if ta.crossover(close, upper)
    strategy.entry("Long", strategy.long)
if ta.crossunder(close, mid)
    strategy.close("Long")"""


def _pine_mean_reversion(name: str, params: dict) -> str:
    period = params.get("period", 20)
    entry_z = params.get("entry_z", -2.0)
    return f"""//@version=5
strategy("{name}", overlay=false)
basis = ta.sma(close, {period})
dev = ta.stdev(close, {period})
z = (close - basis) / dev
plot(z)
hline({entry_z})
hline(0)
if z < {entry_z}
    strategy.entry("Long", strategy.long)
if z > 0
    strategy.close("Long")"""
