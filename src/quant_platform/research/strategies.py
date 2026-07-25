"""Built-in technical analysis strategies — signal generators for backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SignalResult:
    entries: list[bool]
    exits: list[bool]
    name: str
    parameters: dict[str, Any]


def sma_crossover(closes: list[float], fast: int = 20, slow: int = 50) -> SignalResult:
    arr = np.array(closes)
    n = len(arr)
    entries = [False] * n
    exits = [False] * n

    if n < slow + 1:
        return SignalResult(entries=entries, exits=exits, name="sma_crossover", parameters={"fast": fast, "slow": slow})

    fast_sma = np.convolve(arr, np.ones(fast) / fast, mode='valid')
    slow_sma = np.convolve(arr, np.ones(slow) / slow, mode='valid')

    offset = slow - fast
    for i in range(1, len(slow_sma)):
        fast_idx = i + offset
        if fast_idx >= len(fast_sma):
            break
        idx = i + slow - 1
        if idx >= n:
            break
        if fast_sma[fast_idx] > slow_sma[i] and fast_sma[fast_idx - 1] <= slow_sma[i - 1]:
            entries[idx] = True
        elif fast_sma[fast_idx] < slow_sma[i] and fast_sma[fast_idx - 1] >= slow_sma[i - 1]:
            exits[idx] = True

    return SignalResult(entries=entries, exits=exits, name="sma_crossover", parameters={"fast": fast, "slow": slow})


def rsi_reversal(closes: list[float], period: int = 14, oversold: float = 30, overbought: float = 70) -> SignalResult:
    arr = np.array(closes, dtype=float)
    n = len(arr)
    entries = [False] * n
    exits = [False] * n

    if n < period + 2:
        return SignalResult(entries=entries, exits=exits, name="rsi_reversal", parameters={"period": period, "oversold": oversold, "overbought": overbought})

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    rsi_values = [0.0] * (period + 1)
    if avg_loss > 0:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - 100 / (1 + rs))
    else:
        rsi_values.append(100.0)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - 100 / (1 + rs))
        else:
            rsi_values.append(100.0)

    for i in range(1, len(rsi_values)):
        if i >= n:
            break
        if rsi_values[i] > oversold and rsi_values[i - 1] <= oversold:
            entries[i] = True
        elif rsi_values[i] > overbought:
            exits[i] = True

    return SignalResult(entries=entries, exits=exits, name="rsi_reversal", parameters={"period": period, "oversold": oversold, "overbought": overbought})


def macd_signal(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> SignalResult:
    arr = np.array(closes, dtype=float)
    n = len(arr)
    entries = [False] * n
    exits = [False] * n

    if n < slow + signal + 1:
        return SignalResult(entries=entries, exits=exits, name="macd_signal", parameters={"fast": fast, "slow": slow, "signal": signal})

    def ema(data, period):
        result = np.zeros_like(data)
        result[0] = data[0]
        multiplier = 2.0 / (period + 1)
        for i in range(1, len(data)):
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
        return result

    fast_ema = ema(arr, fast)
    slow_ema = ema(arr, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)

    for i in range(slow + signal, n):
        if macd_line[i] > signal_line[i] and macd_line[i - 1] <= signal_line[i - 1]:
            entries[i] = True
        elif macd_line[i] < signal_line[i] and macd_line[i - 1] >= signal_line[i - 1]:
            exits[i] = True

    return SignalResult(entries=entries, exits=exits, name="macd_signal", parameters={"fast": fast, "slow": slow, "signal": signal})


def bollinger_breakout(closes: list[float], period: int = 20, std_dev: float = 2.0) -> SignalResult:
    arr = np.array(closes, dtype=float)
    n = len(arr)
    entries = [False] * n
    exits = [False] * n

    if n < period + 1:
        return SignalResult(entries=entries, exits=exits, name="bollinger_breakout", parameters={"period": period, "std_dev": std_dev})

    for i in range(period, n):
        window = arr[i - period:i]
        mid = np.mean(window)
        std = np.std(window)
        upper = mid + std_dev * std
        lower = mid - std_dev * std

        if arr[i] > upper and arr[i - 1] <= upper:
            entries[i] = True
        elif arr[i] < mid:
            exits[i] = True

    return SignalResult(entries=entries, exits=exits, name="bollinger_breakout", parameters={"period": period, "std_dev": std_dev})


def mean_reversion(closes: list[float], period: int = 20, entry_z: float = -2.0, exit_z: float = 0.0) -> SignalResult:
    arr = np.array(closes, dtype=float)
    n = len(arr)
    entries = [False] * n
    exits = [False] * n

    if n < period + 1:
        return SignalResult(entries=entries, exits=exits, name="mean_reversion", parameters={"period": period, "entry_z": entry_z, "exit_z": exit_z})

    for i in range(period, n):
        window = arr[i - period:i]
        mean = np.mean(window)
        std = np.std(window)
        if std == 0:
            continue
        z = (arr[i] - mean) / std

        if z <= entry_z:
            entries[i] = True
        elif z >= exit_z:
            exits[i] = True

    return SignalResult(entries=entries, exits=exits, name="mean_reversion", parameters={"period": period, "entry_z": entry_z, "exit_z": exit_z})


BUILTIN_STRATEGIES = {
    "sma_crossover": sma_crossover,
    "rsi_reversal": rsi_reversal,
    "macd_signal": macd_signal,
    "bollinger_breakout": bollinger_breakout,
    "mean_reversion": mean_reversion,
}

PARAMETER_GRID = {
    "sma_crossover": [
        {"fast": 10, "slow": 30},
        {"fast": 20, "slow": 50},
        {"fast": 50, "slow": 200},
        {"fast": 5, "slow": 20},
    ],
    "rsi_reversal": [
        {"period": 14, "oversold": 30, "overbought": 70},
        {"period": 14, "oversold": 20, "overbought": 80},
        {"period": 7, "oversold": 30, "overbought": 70},
        {"period": 21, "oversold": 25, "overbought": 75},
    ],
    "macd_signal": [
        {"fast": 12, "slow": 26, "signal": 9},
        {"fast": 8, "slow": 21, "signal": 5},
        {"fast": 5, "slow": 35, "signal": 5},
    ],
    "bollinger_breakout": [
        {"period": 20, "std_dev": 2.0},
        {"period": 20, "std_dev": 1.5},
        {"period": 50, "std_dev": 2.0},
    ],
    "mean_reversion": [
        {"period": 20, "entry_z": -2.0, "exit_z": 0.0},
        {"period": 20, "entry_z": -1.5, "exit_z": 0.5},
        {"period": 50, "entry_z": -2.0, "exit_z": 0.0},
    ],
}
