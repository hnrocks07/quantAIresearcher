"""Contract metadata sync — daily refresh of lot sizes, expiry dates, contract details for any market."""

from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any

from ..database import get_db
from ..models import AssetORM
from ..market_profiles import load_profile, list_profiles
from ..plugins.registry import registry
from ..config import get_settings
from ..logging import get_logger

logger = get_logger("contract_sync")


class ContractSync:

    def __init__(self):
        self._last_sync: dict[str, str] = {}
        self._last_result: dict[str, dict] = {}

    async def sync(self, profile_name: str | None = None) -> dict[str, Any]:
        settings = get_settings()
        if not settings.contract_sync_enabled:
            return {"enabled": False}

        profiles = [profile_name] if profile_name else list_profiles()
        all_results = {}

        for pname in profiles:
            try:
                result = await self._sync_profile(pname)
                all_results[pname] = result
                self._last_sync[pname] = datetime.now(timezone.utc).isoformat()
                self._last_result[pname] = result
            except Exception as e:
                logger.warning(f"Contract sync failed for {pname}: {e}")
                all_results[pname] = {"error": str(e)}

        return {"profiles": all_results, "synced_at": datetime.now(timezone.utc).isoformat()}

    async def _sync_profile(self, profile_name: str) -> dict[str, Any]:
        profile = load_profile(profile_name)
        provider_name = profile.data_provider or get_settings().data_provider
        provider = registry.get_data_provider(provider_name)

        await provider.connect()
        try:
            instruments = await provider.fetch_instruments(exchange=profile.exchange)
        finally:
            await provider.disconnect()

        # Also include static instruments from the profile config
        static = list(profile.instruments)
        all_instruments = instruments + static

        updated = 0
        created = 0
        expired = 0
        errors = []
        today = date.today()

        with get_db() as db:
            for inst in all_instruments:
                try:
                    symbol = inst.get("symbol", "")
                    if not symbol:
                        continue

                    asset = db.query(AssetORM).filter(
                        AssetORM.symbol == symbol,
                        AssetORM.exchange == profile.exchange,
                    ).first()

                    if asset:
                        changed = self._update_if_changed(asset, inst, profile)
                        if changed:
                            updated += 1
                    else:
                        asset = AssetORM(
                            symbol=symbol,
                            name=inst.get("name", symbol),
                            asset_type=inst.get("asset_type", profile.asset_type),
                            exchange=profile.exchange,
                            market_profile=profile.name,
                            currency=inst.get("currency", profile.currency),
                            lot_size=int(inst.get("lot_size", profile.lot_size_default)),
                            tick_size=profile.tick_size_default,
                        )
                        if inst.get("sector"):
                            asset.sector = inst["sector"]
                        if inst.get("expiry_date"):
                            asset.expiry_date = inst["expiry_date"]
                        if inst.get("strike_price"):
                            asset.strike_price = inst["strike_price"]
                        if inst.get("option_type"):
                            asset.option_type = inst["option_type"]
                        if inst.get("contract_type"):
                            asset.contract_type = inst["contract_type"]
                        db.add(asset)
                        created += 1

                except Exception as e:
                    errors.append({"symbol": inst.get("symbol", "?"), "error": str(e)})

            # Mark expired contracts inactive
            expired_assets = db.query(AssetORM).filter(
                AssetORM.exchange == profile.exchange,
                AssetORM.expiry_date != None,
                AssetORM.expiry_date < datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
                AssetORM.is_active == True,
            ).all()
            for asset in expired_assets:
                asset.is_active = False
                expired += 1

            db.flush()

        logger.info(f"Contract sync [{profile_name}]: {created} created, {updated} updated, {expired} expired")
        return {"updated": updated, "created": created, "expired": expired, "errors": errors}

    def _update_if_changed(self, asset: AssetORM, inst: dict, profile) -> bool:
        changed = False
        new_lot = int(inst.get("lot_size", 0))
        if new_lot > 0 and asset.lot_size != new_lot:
            asset.lot_size = new_lot
            changed = True

        new_expiry = inst.get("expiry_date")
        if new_expiry and asset.expiry_date != new_expiry:
            asset.expiry_date = new_expiry
            changed = True

        new_strike = inst.get("strike_price")
        if new_strike and asset.strike_price != new_strike:
            asset.strike_price = new_strike
            changed = True

        new_opt = inst.get("option_type")
        if new_opt and asset.option_type != new_opt:
            asset.option_type = new_opt
            changed = True

        new_ct = inst.get("contract_type")
        if new_ct and asset.contract_type != new_ct:
            asset.contract_type = new_ct
            changed = True

        if not asset.is_active:
            asset.is_active = True
            changed = True

        return changed

    def status(self) -> dict[str, Any]:
        return {
            "last_sync": self._last_sync,
            "last_result": self._last_result,
        }


contract_sync = ContractSync()
