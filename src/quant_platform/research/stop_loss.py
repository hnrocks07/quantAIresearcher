"""ATR-based stop loss calculation."""

from __future__ import annotations

import numpy as np


def calculate_optimal_sl(prices: list[float], period: int = 14) -> dict:
    arr = np.array(prices, dtype=float)
    if len(arr) < period + 1:
        return {"atr": 0.0, "sl_pct": 0.0, "sl_price": 0.0, "method": "atr"}

    tr = []
    for i in range(1, len(arr)):
        tr.append(max(
            arr[i] - arr[i - 1],
            abs(arr[i] - arr[i - 1]),
            abs(arr[i - 1] - arr[i]),
        ))

    atr = float(np.mean(tr[-period:]))
    current_price = arr[-1]
    sl_price = current_price - 2 * atr
    sl_pct = (2 * atr) / current_price if current_price > 0 else 0.0

    return {
        "atr": round(atr, 4),
        "sl_pct": round(sl_pct, 4),
        "sl_price": round(sl_price, 4),
        "method": "atr",
    }
