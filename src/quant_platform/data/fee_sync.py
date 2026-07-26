"""Fee structure sync — keeps brokerage/STT/GST/exchange charges current across all markets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..database import get_db
from ..models import MarketFeeORM
from ..plugins.broker import FeeSchedule
from ..logging import get_logger

logger = get_logger("fee_sync")

KNOWN_FEES: list[dict[str, Any]] = [
    # NSE Equity Delivery
    {"exchange": "NSE", "segment": "equity_delivery", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.001, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00015, "exchange_charge_pct": 0.0000345,
     "sebi_charge_pct": 0.000001, "source": "NSE circular 2026"},
    # NSE Equity Intraday
    {"exchange": "NSE", "segment": "equity_intraday", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.00025, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00003, "exchange_charge_pct": 0.0000345,
     "sebi_charge_pct": 0.000001, "source": "NSE circular 2026"},
    # NSE F&O Futures
    {"exchange": "NSE", "segment": "fno_futures", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.0125, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00003, "exchange_charge_pct": 0.0019,
     "sebi_charge_pct": 0.000001, "source": "NSE circular 2026"},
    # NSE F&O Options
    {"exchange": "NSE", "segment": "fno_options", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.0625, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00003, "exchange_charge_pct": 0.05,
     "sebi_charge_pct": 0.000001, "source": "NSE circular 2026"},
    # BSE Equity Delivery
    {"exchange": "BSE", "segment": "equity_delivery", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.001, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00015, "exchange_charge_pct": 0.0000375,
     "sebi_charge_pct": 0.000001, "source": "BSE circular 2026"},
    # BSE Equity Intraday
    {"exchange": "BSE", "segment": "equity_intraday", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.00025, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00003, "exchange_charge_pct": 0.0000375,
     "sebi_charge_pct": 0.000001, "source": "BSE circular 2026"},
    # MCX Commodity
    {"exchange": "MCX", "segment": "commodity_futures", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.01, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00003, "exchange_charge_pct": 0.0026,
     "sebi_charge_pct": 0.000001, "source": "MCX circular 2026"},
    # MCX Options
    {"exchange": "MCX", "segment": "commodity_options", "commission_per_order": 20.0,
     "commission_pct": 0.0003, "stt_pct": 0.05, "gst_pct": 0.18,
     "stamp_duty_pct": 0.00003, "exchange_charge_pct": 0.0026,
     "sebi_charge_pct": 0.000001, "source": "MCX circular 2026"},
    # Crypto (no Indian tax structure, exchange-specific fees)
    {"exchange": "CRYPTO", "segment": "spot", "commission_per_order": 0.0,
     "commission_pct": 0.001, "stt_pct": 0.0, "gst_pct": 0.0,
     "stamp_duty_pct": 0.0, "exchange_charge_pct": 0.0,
     "sebi_charge_pct": 0.0, "source": "Generic crypto exchange"},
]


class FeeSyncService:

    def __init__(self):
        self._last_sync: str | None = None

    def seed(self) -> dict[str, int]:
        seeded = 0
        updated = 0
        with get_db() as db:
            for fee_data in KNOWN_FEES:
                existing = db.query(MarketFeeORM).filter(
                    MarketFeeORM.exchange == fee_data["exchange"],
                    MarketFeeORM.segment == fee_data["segment"],
                ).first()

                if existing:
                    changed = False
                    for key in ("commission_per_order", "commission_pct", "stt_pct", "gst_pct",
                                "stamp_duty_pct", "exchange_charge_pct", "sebi_charge_pct", "source"):
                        if key in fee_data and getattr(existing, key) != fee_data[key]:
                            setattr(existing, key, fee_data[key])
                            changed = True
                    if changed:
                        updated += 1
                else:
                    db.add(MarketFeeORM(**fee_data))
                    seeded += 1
            db.flush()
        self._last_sync = datetime.now(timezone.utc).isoformat()
        logger.info(f"Fee seed: {seeded} created, {updated} updated")
        return {"seeded": seeded, "updated": updated}

    def get_fee_schedule(self, exchange: str, segment: str = "equity_delivery") -> FeeSchedule:
        with get_db() as db:
            fee = db.query(MarketFeeORM).filter(
                MarketFeeORM.exchange == exchange.upper(),
                MarketFeeORM.segment == segment,
            ).first()

            if fee:
                return FeeSchedule(
                    commission_per_order=fee.commission_per_order,
                    commission_pct=fee.commission_pct,
                    stt_pct=fee.stt_pct,
                    gst_pct=fee.gst_pct,
                    stamp_duty_pct=fee.stamp_duty_pct,
                    exchange_charge_pct=fee.exchange_charge_pct,
                    sebi_charge_pct=fee.sebi_charge_pct,
                )

        return FeeSchedule()

    def update_fee(self, exchange: str, segment: str, updates: dict[str, float]) -> dict[str, Any]:
        allowed = {"commission_per_order", "commission_pct", "stt_pct", "gst_pct",
                    "stamp_duty_pct", "exchange_charge_pct", "sebi_charge_pct", "source"}
        with get_db() as db:
            fee = db.query(MarketFeeORM).filter(
                MarketFeeORM.exchange == exchange.upper(),
                MarketFeeORM.segment == segment,
            ).first()
            if not fee:
                return {"error": f"No fee record for {exchange}/{segment}"}
            changes = {}
            for key, val in updates.items():
                if key in allowed and getattr(fee, key) != val:
                    old = getattr(fee, key)
                    setattr(fee, key, val)
                    changes[key] = {"old": old, "new": val}
            db.flush()
        return {"exchange": exchange, "segment": segment, "changes": changes}

    def get_all_fees(self) -> list[dict[str, Any]]:
        with get_db() as db:
            fees = db.query(MarketFeeORM).all()
            return [
                {
                    "exchange": f.exchange,
                    "segment": f.segment,
                    "commission_per_order": f.commission_per_order,
                    "commission_pct": f.commission_pct,
                    "stt_pct": f.stt_pct,
                    "gst_pct": f.gst_pct,
                    "stamp_duty_pct": f.stamp_duty_pct,
                    "exchange_charge_pct": f.exchange_charge_pct,
                    "sebi_charge_pct": f.sebi_charge_pct,
                    "source": f.source,
                    "updated_at": f.updated_at.isoformat() if f.updated_at else None,
                }
                for f in fees
            ]

    def calculate_roundtrip(self, exchange: str, segment: str, trade_value: float) -> dict[str, Any]:
        fs = self.get_fee_schedule(exchange, segment)
        buy_fees = fs.calculate_total_fees(trade_value, "buy")
        sell_fees = fs.calculate_total_fees(trade_value, "sell")
        total = buy_fees + sell_fees
        breakeven_pct = (total / trade_value) * 100 if trade_value > 0 else 0
        return {
            "exchange": exchange,
            "segment": segment,
            "trade_value": trade_value,
            "buy_fees": round(buy_fees, 2),
            "sell_fees": round(sell_fees, 2),
            "total_roundtrip_fees": round(total, 2),
            "breakeven_pct": round(breakeven_pct, 4),
            "you_keep_pct": round(100 - breakeven_pct, 4),
        }

    def status(self) -> dict[str, Any]:
        return {"last_sync": self._last_sync, "fee_count": len(self.get_all_fees())}


fee_sync = FeeSyncService()
