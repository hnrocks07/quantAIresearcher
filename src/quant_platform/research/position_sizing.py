"""Position sizing using ATR-based volatility."""

from __future__ import annotations

import numpy as np


def calculate_position_size(
    prices: list[float],
    capital: float,
    risk_pct: float = 0.02,
) -> dict:
    arr = np.array(prices, dtype=float)
    if len(arr) < 15:
        return {"position_size": 0, "risk_per_trade": 0.0, "atr": 0.0, "stop_distance": 0.0}

    highs = arr[1:]
    lows = arr[:-1]
    prev_close = arr[:-1]
    current = arr[1:]

    tr = np.maximum(
        highs - lows,
        np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)),
    )

    period = 14
    if len(tr) < period:
        return {"position_size": 0, "risk_per_trade": 0.0, "atr": 0.0, "stop_distance": 0.0}

    atr = float(np.mean(tr[-period:]))
    stop_distance = 2 * atr
    risk_per_trade = capital * risk_pct
    position_size = int(risk_per_trade / stop_distance) if stop_distance > 0 else 0

    return {
        "position_size": position_size,
        "risk_per_trade": round(risk_per_trade, 2),
        "atr": round(atr, 4),
        "stop_distance": round(stop_distance, 4),
    }
