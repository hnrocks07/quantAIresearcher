"""Tests for JugaadNSEProvider — all mocked, no real network calls."""

from __future__ import annotations

import asyncio
import csv
import io
import os
import sys
import tempfile
import types
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Ensure jugaad_data is available as a mock module for patching,
# even when the real package is not installed.
if "jugaad_data" not in sys.modules:
    _jd = types.ModuleType("jugaad_data")
    _jd_nse = types.ModuleType("jugaad_data.nse")
    _jd_nse.bhavcopy_fo_save = MagicMock()
    _jd_nse.stock_df = MagicMock()
    _jd.nse = _jd_nse
    sys.modules["jugaad_data"] = _jd
    sys.modules["jugaad_data.nse"] = _jd_nse

from quant_platform.data.jugaad_provider import (
    JugaadNSEProvider,
    _is_fno_symbol,
    _instrument_to_asset_type,
    _parse_fno_row,
    _parse_instruments_from_csv,
    _safe_float,
    RATE_LIMIT_DELAY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


SAMPLE_FO_CSV = """\
INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP
FUTIDX,NIFTY,31-Jul-2026,0.00,XX,24500.00,24700.00,24400.00,24650.00,24650.00,150000,1200000.00,8000000,50000,25-Jul-2026
FUTSTK,RELIANCE,31-Jul-2026,0.00,XX,2800.00,2850.00,2780.00,2830.00,2830.00,50000,300000.00,2000000,10000,25-Jul-2026
OPTIDX,NIFTY,31-Jul-2026,24500.00,CE,200.00,250.00,180.00,230.00,230.00,80000,500000.00,5000000,20000,25-Jul-2026
OPTIDX,NIFTY,31-Jul-2026,24500.00,PE,150.00,180.00,130.00,160.00,160.00,60000,400000.00,4000000,15000,25-Jul-2026
OPTSTK,RELIANCE,31-Jul-2026,2800.00,CE,50.00,65.00,45.00,60.00,60.00,30000,200000.00,1000000,5000,25-Jul-2026
"""


def _write_sample_csv(directory: str, content: str = SAMPLE_FO_CSV) -> str:
    """Write sample CSV to a temp directory and return file path."""
    path = os.path.join(directory, "fo_bhav.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Test: name()
# ---------------------------------------------------------------------------

class TestName:

    def test_name_returns_jugaad_nse(self):
        p = JugaadNSEProvider()
        assert p.name() == "jugaad_nse"


# ---------------------------------------------------------------------------
# Test: connect/disconnect are no-op
# ---------------------------------------------------------------------------

class TestConnectDisconnect:

    def test_connect_disconnect_no_error(self):
        p = JugaadNSEProvider()
        _run(p.connect())
        _run(p.disconnect())
        assert p._instruments_cache is None


# ---------------------------------------------------------------------------
# Test: fetch_instruments parses F&O bhav copy CSV
# ---------------------------------------------------------------------------

class TestFetchInstruments:

    def test_parses_fno_bhav_copy_csv(self):
        p = JugaadNSEProvider()

        def mock_bhavcopy_fo_save(dt, path):
            _write_sample_csv(path)

        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            with patch(
                "jugaad_data.nse.bhavcopy_fo_save",
                side_effect=mock_bhavcopy_fo_save,
            ):
                result = _run(p.fetch_instruments(exchange="NSE_FNO"))

        assert len(result) == 5
        symbols = [r["symbol"] for r in result]
        assert "NIFTY" in symbols
        assert "RELIANCE" in symbols

        # Check asset types
        futures = [r for r in result if r["asset_type"] == "futures"]
        options = [r for r in result if r["asset_type"] == "options"]
        assert len(futures) == 2  # FUTIDX NIFTY + FUTSTK RELIANCE
        assert len(options) == 3  # OPTIDX NIFTY CE + PE + OPTSTK RELIANCE CE

        # Check F&O fields populated
        nifty_opt_ce = [
            r for r in result
            if r["symbol"] == "NIFTY"
            and r.get("option_type") == "CE"
        ]
        assert len(nifty_opt_ce) == 1
        assert nifty_opt_ce[0]["strike_price"] == 24500.0
        assert nifty_opt_ce[0]["expiry_date"] == date(2026, 7, 31)
        assert nifty_opt_ce[0]["contract_type"] == "OPTIDX"
        assert nifty_opt_ce[0]["currency"] == "INR"
        assert nifty_opt_ce[0]["exchange"] == "NSE"

    def test_returns_empty_when_jugaad_not_installed(self):
        p = JugaadNSEProvider()
        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=False,
        ):
            result = _run(p.fetch_instruments())
        assert result == []

    def test_caches_instruments(self):
        p = JugaadNSEProvider()
        cached = [{"symbol": "NIFTY", "name": "NIFTY", "asset_type": "futures"}]
        p._instruments_cache = cached
        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            result = _run(p.fetch_instruments())
        assert result is cached


# ---------------------------------------------------------------------------
# Test: fetch_ohlcv for equity (mock stock_df)
# ---------------------------------------------------------------------------

class TestFetchOHLCVEquity:

    def test_fetch_equity_ohlcv_uses_stock_df(self):
        p = JugaadNSEProvider()

        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.__len__ = MagicMock(return_value=2)
        mock_df.iterrows.return_value = [
            (0, {
                "DATE": date(2026, 7, 21),
                "OPEN": 2800.0, "HIGH": 2850.0,
                "LOW": 2780.0, "CLOSE": 2830.0,
                "VOLUME": 5000000.0,
            }),
            (1, {
                "DATE": date(2026, 7, 22),
                "OPEN": 2830.0, "HIGH": 2860.0,
                "LOW": 2810.0, "CLOSE": 2845.0,
                "VOLUME": 4500000.0,
            }),
        ]

        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            with patch(
                "jugaad_data.nse.stock_df",
                return_value=mock_df,
            ) as mock_stock:
                result = _run(
                    p.fetch_ohlcv("RELIANCE", date(2026, 7, 21), date(2026, 7, 22))
                )
                mock_stock.assert_called_once_with(
                    symbol="RELIANCE",
                    from_date=date(2026, 7, 21),
                    to_date=date(2026, 7, 22),
                    series="EQ",
                )

        assert len(result) == 2
        assert result[0]["open"] == 2800.0
        assert result[0]["close"] == 2830.0
        assert result[1]["volume"] == 4500000.0


# ---------------------------------------------------------------------------
# Test: fetch_ohlcv for F&O (mock bhavcopy_fo_save)
# ---------------------------------------------------------------------------

class TestFetchOHLCVFnO:

    def test_fetch_fno_ohlcv_parses_csv(self):
        p = JugaadNSEProvider()

        call_dates = []

        def mock_bhavcopy_fo_save(dt, path):
            call_dates.append(dt)
            # Write CSV with NIFTY FUT row
            csv_content = (
                "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,"
                "SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP\n"
                f"FUTIDX,NIFTY,31-Jul-2026,0.00,XX,24500.00,24700.00,24400.00,24650.00,"
                f"24650.00,150000,1200000.00,8000000,50000,{dt.strftime('%d-%b-%Y')}\n"
            )
            path_f = os.path.join(path, "fo_bhav.csv")
            with open(path_f, "w") as f:
                f.write(csv_content)

        # Use a symbol with FUT to trigger F&O path
        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            with patch(
                "jugaad_data.nse.bhavcopy_fo_save",
                side_effect=mock_bhavcopy_fo_save,
            ):
                # Mon Jul 20 to Wed Jul 22 (3 weekdays)
                result = _run(
                    p.fetch_ohlcv(
                        "NIFTY FUT",
                        date(2026, 7, 20),
                        date(2026, 7, 22),
                    )
                )

        assert len(result) == 3
        assert result[0]["open"] == 24500.0
        assert result[0]["close"] == 24650.0
        assert result[0]["open_interest"] == 8000000.0
        assert result[0]["settle_price"] == 24650.0
        assert result[0]["contracts"] == 150000.0


# ---------------------------------------------------------------------------
# Test: search_symbol
# ---------------------------------------------------------------------------

class TestSearchSymbol:

    def test_search_filters_correctly(self):
        p = JugaadNSEProvider()
        p._instruments_cache = [
            {"symbol": "NIFTY", "name": "NIFTY", "asset_type": "futures"},
            {"symbol": "BANKNIFTY", "name": "BANKNIFTY", "asset_type": "futures"},
            {"symbol": "RELIANCE", "name": "RELIANCE", "asset_type": "futures"},
        ]

        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            result = _run(p.search_symbol("NIFTY"))

        assert len(result) == 2
        symbols = [r["symbol"] for r in result]
        assert "NIFTY" in symbols
        assert "BANKNIFTY" in symbols
        assert "RELIANCE" not in symbols

    def test_search_case_insensitive(self):
        p = JugaadNSEProvider()
        p._instruments_cache = [
            {"symbol": "NIFTY", "name": "NIFTY", "asset_type": "futures"},
        ]

        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            result = _run(p.search_symbol("nifty"))

        assert len(result) == 1


# ---------------------------------------------------------------------------
# Test: graceful ImportError handling
# ---------------------------------------------------------------------------

class TestImportErrorHandling:

    def test_fetch_ohlcv_returns_empty_when_not_installed(self):
        p = JugaadNSEProvider()
        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=False,
        ):
            result = _run(
                p.fetch_ohlcv("RELIANCE", date(2026, 7, 1), date(2026, 7, 5))
            )
        assert result == []

    def test_fetch_instruments_returns_empty_when_not_installed(self):
        p = JugaadNSEProvider()
        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=False,
        ):
            result = _run(p.fetch_instruments())
        assert result == []


# ---------------------------------------------------------------------------
# Test: date skipping (weekends)
# ---------------------------------------------------------------------------

class TestDateSkipping:

    def test_skips_weekends_in_fno_ohlcv(self):
        p = JugaadNSEProvider()
        call_dates = []

        def mock_bhavcopy_fo_save(dt, path):
            call_dates.append(dt)
            # Write minimal CSV
            csv_content = (
                "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,"
                "SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP\n"
                f"FUTIDX,NIFTY,31-Jul-2026,0.00,XX,100,100,100,100,"
                f"100,100,100,100,0,{dt.strftime('%d-%b-%Y')}\n"
            )
            with open(os.path.join(path, "fo_bhav.csv"), "w") as f:
                f.write(csv_content)

        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            with patch(
                "jugaad_data.nse.bhavcopy_fo_save",
                side_effect=mock_bhavcopy_fo_save,
            ):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    # Fri Jul 24 to Mon Jul 27 — should only call Fri and Mon
                    _run(
                        p.fetch_ohlcv(
                            "NIFTY FUT",
                            date(2026, 7, 24),
                            date(2026, 7, 27),
                        )
                    )

        # Sat 25 and Sun 26 should be skipped
        weekdays_called = [d.weekday() for d in call_dates]
        assert 5 not in weekdays_called  # no Saturday
        assert 6 not in weekdays_called  # no Sunday
        assert len(call_dates) == 2  # Fri + Mon


# ---------------------------------------------------------------------------
# Test: rate limiting delay exists
# ---------------------------------------------------------------------------

class TestRateLimiting:

    def test_rate_limit_delay_constant(self):
        assert RATE_LIMIT_DELAY == 0.3

    def test_sleep_called_between_fno_requests(self):
        p = JugaadNSEProvider()

        def mock_bhavcopy_fo_save(dt, path):
            csv_content = (
                "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,"
                "SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP\n"
                f"FUTIDX,NIFTY,31-Jul-2026,0.00,XX,100,100,100,100,"
                f"100,100,100,100,0,{dt.strftime('%d-%b-%Y')}\n"
            )
            with open(os.path.join(path, "fo_bhav.csv"), "w") as f:
                f.write(csv_content)

        with patch(
            "quant_platform.data.jugaad_provider._is_jugaad_available",
            return_value=True,
        ):
            with patch(
                "jugaad_data.nse.bhavcopy_fo_save",
                side_effect=mock_bhavcopy_fo_save,
            ):
                with patch(
                    "quant_platform.data.jugaad_provider.asyncio.sleep",
                    new_callable=AsyncMock,
                ) as mock_sleep:
                    # Two weekdays: Mon Jul 20, Tue Jul 21
                    _run(
                        p.fetch_ohlcv(
                            "NIFTY FUT",
                            date(2026, 7, 20),
                            date(2026, 7, 21),
                        )
                    )
                    # sleep should be called with RATE_LIMIT_DELAY
                    assert mock_sleep.call_count == 2
                    mock_sleep.assert_any_call(RATE_LIMIT_DELAY)


# ---------------------------------------------------------------------------
# Test: helper functions
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_is_fno_symbol(self):
        assert _is_fno_symbol("NIFTY FUT") is True
        assert _is_fno_symbol("RELIANCE OPT") is True
        assert _is_fno_symbol("NIFTY CE") is True
        assert _is_fno_symbol("NIFTY PE") is True
        assert _is_fno_symbol("NIFTY24500CE") is False  # CE not as word boundary
        assert _is_fno_symbol("RELIANCE") is False
        assert _is_fno_symbol("TCS") is False
        assert _is_fno_symbol("PERSISTENT") is False  # contains "PE" but not as word

    def test_instrument_to_asset_type(self):
        assert _instrument_to_asset_type("FUTIDX") == "futures"
        assert _instrument_to_asset_type("FUTSTK") == "futures"
        assert _instrument_to_asset_type("OPTIDX") == "options"
        assert _instrument_to_asset_type("OPTSTK") == "options"
        assert _instrument_to_asset_type("UNKNOWN") == "futures"

    def test_safe_float(self):
        assert _safe_float("123.45") == 123.45
        assert _safe_float(None) == 0.0
        assert _safe_float("") == 0.0
        assert _safe_float("abc") == 0.0
        assert _safe_float(42) == 42.0

    def test_parse_fno_row(self):
        row = {
            "INSTRUMENT": "FUTIDX",
            "SYMBOL": "NIFTY",
            "EXPIRY_DT": "31-Jul-2026",
            "STRIKE_PR": "0.00",
            "OPTION_TYP": "XX",
            "OPEN": "24500.00",
            "HIGH": "24700.00",
            "LOW": "24400.00",
            "CLOSE": "24650.00",
            "SETTLE_PR": "24650.00",
            "CONTRACTS": "150000",
            "VAL_INLAKH": "1200000.00",
            "OPEN_INT": "8000000",
            "CHG_IN_OI": "50000",
        }
        result = _parse_fno_row(row, date(2026, 7, 25))
        assert result["date"] == date(2026, 7, 25)
        assert result["open"] == 24500.0
        assert result["close"] == 24650.0
        assert result["open_interest"] == 8000000.0
        assert result["expiry_date"] == date(2026, 7, 31)
        assert result["symbol"] == "NIFTY"

    def test_parse_instruments_from_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _write_sample_csv(tmpdir)
            instruments = _parse_instruments_from_csv(csv_path)

        assert len(instruments) == 5
        futures = [i for i in instruments if i["asset_type"] == "futures"]
        options = [i for i in instruments if i["asset_type"] == "options"]
        assert len(futures) == 2
        assert len(options) == 3
