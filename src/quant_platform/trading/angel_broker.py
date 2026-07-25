"""Angel One broker adapter using SmartAPI."""

from __future__ import annotations

import logging
from typing import Any

from ..plugins.broker import BrokerAdapter, FeeSchedule, OrderResult

logger = logging.getLogger("angel_broker")

_SMART_AVAILABLE = True
try:
    from SmartApi import SmartConnect
except ImportError:
    _SMART_AVAILABLE = False
    SmartConnect = None
    logger.warning("smartapi-python not installed, AngelBroker unavailable")

_PYOTP_AVAILABLE = True
try:
    import pyotp
except ImportError:
    _PYOTP_AVAILABLE = False
    pyotp = None


class AngelBroker(BrokerAdapter):

    def __init__(
        self,
        api_key: str = "",
        client_id: str = "",
        pin: str = "",
        totp_secret: str = "",
    ):
        self._api_key = api_key
        self._client_id = client_id
        self._pin = pin
        self._totp_secret = totp_secret
        self._smart: Any = None

    def name(self) -> str:
        return "angel"

    def fee_schedule(self) -> FeeSchedule:
        return FeeSchedule(
            commission_per_order=20.0,
            stt_pct=0.001,
            gst_pct=0.18,
            exchange_charge_pct=0.0019,
            sebi_charge_pct=0.000001,
            stamp_duty_pct=0.00003,
        )

    async def connect(self) -> None:
        if not _SMART_AVAILABLE:
            raise RuntimeError("smartapi-python not installed")
        if not _PYOTP_AVAILABLE:
            raise RuntimeError("pyotp not installed")

        self._smart = SmartConnect(api_key=self._api_key)
        totp = pyotp.TOTP(self._totp_secret).now()
        self._smart.generateSession(self._client_id, self._pin, totp)
        logger.info(f"Connected to Angel One as {self._client_id}")

    async def disconnect(self) -> None:
        if self._smart:
            try:
                self._smart.terminateSession(self._client_id)
            except Exception as e:
                logger.warning(f"Error terminating session: {e}")
            self._smart = None

    async def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str,
        price: float | None = None,
    ) -> OrderResult:
        if not self._smart:
            return OrderResult(order_id="", status="error", message="Not connected")

        params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": "",
            "transactiontype": "BUY" if side in ("buy", "long") else "SELL",
            "exchange": "NSE",
            "ordertype": order_type.upper(),
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": price or 0,
            "quantity": int(qty),
        }
        try:
            result = self._smart.placeOrder(params)
            return OrderResult(
                order_id=str(result) if result else "",
                status="placed",
                filled_qty=qty,
            )
        except Exception as e:
            return OrderResult(order_id="", status="error", message=str(e))

    async def cancel_order(self, order_id: str) -> bool:
        if not self._smart:
            return False
        try:
            self._smart.cancelOrder("NORMAL", order_id)
            return True
        except Exception:
            return False

    async def order_status(self, order_id: str) -> dict[str, Any]:
        if not self._smart:
            return {"error": "Not connected"}
        try:
            book = self._smart.orderBook()
            if book and book.get("data"):
                for order in book["data"]:
                    if str(order.get("orderid")) == order_id:
                        return order
            return {"error": "Order not found"}
        except Exception as e:
            return {"error": str(e)}

    async def positions(self) -> list[dict[str, Any]]:
        if not self._smart:
            return []
        try:
            result = self._smart.position()
            if result and result.get("data"):
                return result["data"]
            return []
        except Exception:
            return []

    async def balance(self) -> dict[str, float]:
        if not self._smart:
            return {"error": -1}
        try:
            result = self._smart.rmsLimit()
            if result and result.get("data"):
                data = result["data"]
                return {
                    "available_cash": float(data.get("availablecash", 0)),
                    "used_margin": float(data.get("utiliseddebits", 0)),
                    "net": float(data.get("net", 0)),
                }
            return {}
        except Exception:
            return {}

    async def quote(self, symbol: str) -> dict[str, float]:
        if not self._smart:
            return {}
        try:
            result = self._smart.ltpData("NSE", symbol, "")
            if result and result.get("data"):
                return {"ltp": float(result["data"].get("ltp", 0))}
            return {}
        except Exception:
            return {}
