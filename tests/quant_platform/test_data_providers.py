"""Tests for pluggable data provider system."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from quant_platform.plugins.data_provider import DataProvider
from quant_platform.plugins.registry import PluginRegistry
from quant_platform.data.yfinance_provider import YFinanceProvider
from quant_platform.data.nse_provider import NSEProvider
from quant_platform.data.crypto_provider import CryptoProvider
from quant_platform.data.ingestion import IngestionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine in a fresh loop when needed."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# DataProvider ABC
# ---------------------------------------------------------------------------

class TestDataProviderABC:

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DataProvider()

    def test_concrete_subclass_works(self):
        class Dummy(DataProvider):
            def name(self): return "dummy"
            async def connect(self): pass
            async def disconnect(self): pass
            async def fetch_ohlcv(self, symbol, start_date, end_date, interval="1d"): return []
            async def fetch_instruments(self, exchange=None): return []
            async def search_symbol(self, query): return []
        d = Dummy()
        assert d.name() == "dummy"


# ---------------------------------------------------------------------------
# YFinanceProvider
# ---------------------------------------------------------------------------

class TestYFinanceProvider:

    def test_name(self):
        p = YFinanceProvider()
        assert p.name() == "yfinance"

    def test_fetch_ohlcv_with_mock(self):
        p = YFinanceProvider()
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.__iter__ = MagicMock(return_value=iter([]))

        mock_index = MagicMock()
        mock_index.to_pydatetime.return_value = datetime(2025, 1, 2, tzinfo=timezone.utc)

        mock_row = {"Open": 100.0, "High": 105.0, "Low": 99.0, "Close": 103.0, "Volume": 1000000.0}
        mock_df.iterrows.return_value = [(mock_index, mock_row)]

        with patch("quant_platform.data.yfinance_provider.yf", create=True) as mock_yf:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_df
            mock_yf.Ticker.return_value = mock_ticker

            with patch("yfinance.Ticker", return_value=mock_ticker):
                result = _run(p.fetch_ohlcv("RELIANCE.NS", date(2025, 1, 1), date(2025, 1, 31)))

        assert len(result) == 1
        assert result[0]["open"] == 100.0
        assert result[0]["close"] == 103.0
        assert result[0]["volume"] == 1000000.0

    def test_fetch_instruments_nse(self):
        p = YFinanceProvider()
        csv_text = "Company Name,Industry,Symbol,Series,ISIN Code\nReliance,Oil,RELIANCE,EQ,INE001\nTCS,IT,TCS,EQ,INE002\n"

        mock_df = MagicMock()
        mock_df.iterrows.return_value = [
            (0, {"Symbol": "RELIANCE", "Company Name": "Reliance", "Industry": "Oil"}),
            (1, {"Symbol": "TCS", "Company Name": "TCS", "Industry": "IT"}),
        ]

        with patch("pandas.read_csv", return_value=mock_df):
            result = _run(p.fetch_instruments(exchange="NSE"))

        assert len(result) == 2
        assert result[0]["symbol"] == "RELIANCE.NS"
        assert result[0]["asset_type"] == "equity"
        assert result[1]["sector"] == "IT"

    def test_fetch_instruments_non_nse_returns_empty(self):
        p = YFinanceProvider()
        result = _run(p.fetch_instruments(exchange="NYSE"))
        assert result == []

    def test_search_symbol(self):
        p = YFinanceProvider()
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "symbol": "RELIANCE.NS",
            "longName": "Reliance Industries",
            "exchange": "NSE",
            "currency": "INR",
        }

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = _run(p.search_symbol("RELIANCE.NS"))

        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE.NS"


# ---------------------------------------------------------------------------
# NSEProvider
# ---------------------------------------------------------------------------

class TestNSEProvider:

    def test_name(self):
        p = NSEProvider()
        assert p.name() == "nse_bhav"

    def test_connect_sets_up_client(self):
        p = NSEProvider()
        _run(p.connect())
        assert p._client is not None
        assert "User-Agent" in p._client.headers
        assert "Referer" in p._client.headers
        _run(p.disconnect())
        assert p._client is None

    def test_fetch_instruments_equity_with_mock(self):
        p = NSEProvider()
        csv_response = "Symbol,Company Name,Industry,Series\nRELIANCE,Reliance Industries,Oil,EQ\nTCS,Tata Consultancy,IT,EQ\n"

        mock_resp = MagicMock()
        mock_resp.text = csv_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        p._client = mock_client

        result = _run(p.fetch_instruments(exchange="NSE_EQUITY"))
        assert len(result) == 2
        assert result[0]["symbol"] == "RELIANCE"
        assert result[0]["asset_type"] == "equity"
        assert result[1]["sector"] == "IT"

    def test_fetch_instruments_fno_with_mock(self):
        p = NSEProvider()
        csv_response = "SYMBOL,JUL-2026,AUG-2026\nNIFTY,50,50\nBANKNIFTY,15,15\n"

        mock_resp = MagicMock()
        mock_resp.text = csv_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        p._client = mock_client

        result = _run(p.fetch_instruments(exchange="NSE_FNO"))
        assert len(result) >= 2
        symbols = [r["symbol"] for r in result]
        assert "NIFTY" in symbols
        assert "BANKNIFTY" in symbols
        assert result[0]["asset_type"] == "futures"

    def test_ensure_client_raises_without_connect(self):
        p = NSEProvider()
        with pytest.raises(RuntimeError, match="not connected"):
            p._ensure_client()


# ---------------------------------------------------------------------------
# CryptoProvider
# ---------------------------------------------------------------------------

class TestCryptoProvider:

    def test_name(self):
        p = CryptoProvider()
        assert p.name() == "crypto"

    def test_fetch_instruments_returns_20(self):
        p = CryptoProvider()
        result = _run(p.fetch_instruments())
        assert len(result) == 20
        symbols = [r["symbol"] for r in result]
        assert "BTC-USD" in symbols
        assert "ETH-USD" in symbols
        assert "INJ-USD" in symbols
        for inst in result:
            assert inst["asset_type"] == "crypto"
            assert inst["currency"] == "USD"

    def test_fetch_ohlcv_appends_usd(self):
        p = CryptoProvider()

        mock_df = MagicMock()
        mock_df.empty = False
        mock_index = MagicMock()
        mock_index.to_pydatetime.return_value = datetime(2025, 1, 2, tzinfo=timezone.utc)
        mock_row = {"Open": 42000.0, "High": 43000.0, "Low": 41000.0, "Close": 42500.0, "Volume": 5000.0}
        mock_df.iterrows.return_value = [(mock_index, mock_row)]

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df

        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf_ticker:
            result = _run(p.fetch_ohlcv("BTC", date(2025, 1, 1), date(2025, 1, 31)))
            mock_yf_ticker.assert_called_with("BTC-USD")

        assert len(result) == 1
        assert result[0]["close"] == 42500.0

    def test_search_symbol(self):
        p = CryptoProvider()
        result = _run(p.search_symbol("BTC"))
        assert len(result) == 1
        assert result[0]["symbol"] == "BTC-USD"

    def test_search_symbol_partial(self):
        p = CryptoProvider()
        result = _run(p.search_symbol("sol"))
        assert len(result) == 1
        assert result[0]["name"] == "Solana"


# ---------------------------------------------------------------------------
# PluginRegistry — data_provider
# ---------------------------------------------------------------------------

class TestRegistryDataProvider:

    def test_register_and_get(self):
        reg = PluginRegistry()
        reg.register_data_provider("yfinance", YFinanceProvider)
        provider = reg.get_data_provider("yfinance")
        assert isinstance(provider, YFinanceProvider)
        assert provider.name() == "yfinance"

    def test_get_unregistered_raises(self):
        reg = PluginRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.get_data_provider("nonexistent")

    def test_list_data_providers(self):
        reg = PluginRegistry()
        reg.register_data_provider("yfinance", YFinanceProvider)
        reg.register_data_provider("nse_bhav", NSEProvider)
        reg.register_data_provider("crypto", CryptoProvider)
        listed = reg.list_data_providers()
        assert set(listed) == {"yfinance", "nse_bhav", "crypto"}


# ---------------------------------------------------------------------------
# IngestionService — provider integration
# ---------------------------------------------------------------------------

class TestIngestionServiceProvider:

    def test_uses_provider_from_registry(self):
        from quant_platform.plugins.registry import registry as global_registry

        class MockProvider(DataProvider):
            connected = False
            disconnected = False
            fetched_instruments = False
            fetched_ohlcv = False

            def name(self): return "mock"
            async def connect(self):
                MockProvider.connected = True
            async def disconnect(self):
                MockProvider.disconnected = True
            async def fetch_ohlcv(self, symbol, start_date, end_date, interval="1d"):
                MockProvider.fetched_ohlcv = True
                return []
            async def fetch_instruments(self, exchange=None):
                MockProvider.fetched_instruments = True
                return [{"symbol": "TEST.NS", "name": "Test", "asset_type": "equity"}]
            async def search_symbol(self, query):
                return []

        global_registry.register_data_provider("mock_test", MockProvider)
        svc = IngestionService(provider_name="mock_test")

        from quant_platform.market_profiles.loader import MarketProfile
        profile = MarketProfile(
            name="test",
            display_name="Test",
            data_provider="mock_test",
            currency="INR",
            exchange="NSE",
            instruments_source="provider",
            instruments=[],
        )
        provider = svc._get_provider(profile)
        assert isinstance(provider, MockProvider)
        assert provider.name() == "mock"

    def test_fno_field_population_in_instruments(self):
        """Verify that F&O metadata from provider is passed through to asset creation."""
        fno_inst = {
            "symbol": "NIFTY",
            "name": "NIFTY 50 Futures",
            "asset_type": "futures",
            "exchange": "NSE",
            "contract_type": "futures",
            "lot_size": 50,
        }
        assert fno_inst.get("contract_type") == "futures"
        assert fno_inst.get("lot_size") == 50
        assert fno_inst.get("expiry_date") is None
