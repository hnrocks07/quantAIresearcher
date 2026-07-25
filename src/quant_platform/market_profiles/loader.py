"""Market profile loader — reads YAML configs defining markets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROFILES_DIR = Path(__file__).parent / "configs"


@dataclass
class MarketProfile:
    name: str
    display_name: str
    data_provider: str
    currency: str
    exchange: str
    trading_hours: dict[str, str] = field(default_factory=dict)
    fee_defaults: dict[str, float] = field(default_factory=dict)
    instruments_source: str = "static"
    instruments_file: str | None = None
    instruments: list[dict[str, str]] = field(default_factory=list)
    lot_size_default: int = 1
    tick_size_default: float = 0.05
    holidays_file: str | None = None
    history_years: int = 20
    asset_type: str = "equity"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MarketProfile:
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            data_provider=data["data_provider"],
            currency=data.get("currency", "INR"),
            exchange=data.get("exchange", "NSE"),
            trading_hours=data.get("trading_hours", {}),
            fee_defaults=data.get("fee_defaults", {}),
            instruments_source=data.get("instruments_source", "static"),
            instruments_file=data.get("instruments_file"),
            instruments=data.get("instruments", []),
            lot_size_default=data.get("lot_size_default", 1),
            tick_size_default=data.get("tick_size_default", 0.05),
            holidays_file=data.get("holidays_file"),
            history_years=data.get("history_years", 20),
            asset_type=data.get("asset_type", "equity"),
        )


def load_profile(name: str) -> MarketProfile:
    config_file = PROFILES_DIR / f"{name}.json"
    if not config_file.exists():
        raise FileNotFoundError(f"Market profile '{name}' not found at {config_file}")
    data = json.loads(config_file.read_text())
    return MarketProfile.from_dict(data)


def list_profiles() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return [f.stem for f in PROFILES_DIR.glob("*.json")]
