"""Market regime classification using SMA slope."""

from __future__ import annotations

import numpy as np


def classify_regime(prices: list[float], window: int = 50) -> str:
    arr = np.array(prices, dtype=float)
    if len(arr) < window + 1:
        return "sideways"

    sma = np.convolve(arr, np.ones(window) / window, mode='valid')
    if len(sma) < 2:
        return "sideways"

    slope = sma[-1] - sma[-2]
    threshold = sma[-1] * 0.001

    if slope > threshold:
        return "bullish"
    elif slope < -threshold:
        return "bearish"
    return "sideways"


def classify_history(prices: list[float], dates: list, window: int = 50) -> list[dict]:
    arr = np.array(prices, dtype=float)
    results = []

    if len(arr) < window + 1:
        return results

    sma = np.convolve(arr, np.ones(window) / window, mode='valid')

    for i in range(1, len(sma)):
        slope = sma[i] - sma[i - 1]
        threshold = sma[i] * 0.001
        date_idx = i + window - 1

        if date_idx >= len(dates):
            break

        if slope > threshold:
            regime = "bullish"
        elif slope < -threshold:
            regime = "bearish"
        else:
            regime = "sideways"

        results.append({"date": dates[date_idx], "regime": regime})

    return results
