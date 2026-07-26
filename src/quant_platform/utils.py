"""Shared utilities — retry with exponential backoff."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger("utils")

T = TypeVar("T")


async def retry_async(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    label: str = "operation",
    **kwargs: Any,
) -> Any:
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt == max_retries:
                break
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.debug(f"{label} attempt {attempt + 1} failed: {e}, retrying in {delay:.1f}s")
            await asyncio.sleep(delay)

    logger.warning(f"{label} failed after {max_retries + 1} attempts: {last_error}")
    raise last_error


def snap_to_lot(qty: int | float, lot_size: int) -> int:
    if lot_size <= 1:
        return max(1, int(qty))
    lots = int(qty) // lot_size
    return max(lot_size, lots * lot_size)
