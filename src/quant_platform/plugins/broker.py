"""BrokerAdapter abstract interface — swap brokers via config."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FeeSchedule:
    commission_per_order: float = 0.0
    commission_pct: float = 0.0
    stt_pct: float = 0.0
    gst_pct: float = 0.18
    stamp_duty_pct: float = 0.0
    exchange_charge_pct: float = 0.0
    sebi_charge_pct: float = 0.0
    other_charges: dict[str, float] = field(default_factory=dict)

    def calculate_total_fees(self, trade_value: float, side: str) -> float:
        fees = self.commission_per_order + (trade_value * self.commission_pct)
        if side in ("sell", "short"):
            fees += trade_value * self.stt_pct
        fees += trade_value * self.exchange_charge_pct
        fees += trade_value * self.sebi_charge_pct
        fees += trade_value * self.stamp_duty_pct
        gst_base = (trade_value * self.commission_pct) + (trade_value * self.exchange_charge_pct)
        fees += gst_base * self.gst_pct
        for charge in self.other_charges.values():
            fees += charge
        return round(fees, 2)


@dataclass
class OrderResult:
    order_id: str
    status: str
    filled_qty: float = 0.0
    filled_price: float = 0.0
    message: str = ""


class BrokerAdapter(ABC):

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fee_schedule(self) -> FeeSchedule: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def place_order(self, symbol: str, side: str, qty: float, order_type: str, price: float | None = None) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def order_status(self, order_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def balance(self) -> dict[str, float]: ...

    @abstractmethod
    async def quote(self, symbol: str) -> dict[str, float]: ...
