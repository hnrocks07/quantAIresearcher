"""Unit tests for quant platform core domain models."""

import pytest
from quant_platform.models import (
    Asset, AssetType, OrderType, Portfolio, Position, PositionStatus, Side, Trade,
)


class TestAsset:

    def test_create_equity(self):
        a = Asset(symbol="RELIANCE", name="Reliance Industries")
        assert a.symbol == "RELIANCE"
        assert a.asset_type == AssetType.EQUITY
        assert a.exchange == "NSE"
        assert a.currency == "INR"
        assert a.is_active is True

    def test_symbol_uppercased(self):
        a = Asset(symbol="infy", name="Infosys")
        assert a.symbol == "INFY"

    def test_symbol_stripped(self):
        a = Asset(symbol="  TCS  ", name="TCS")
        assert a.symbol == "TCS"

    def test_empty_symbol_rejected(self):
        with pytest.raises(ValueError, match="symbol must not be empty"):
            Asset(symbol="", name="Empty")

    def test_negative_lot_size_rejected(self):
        with pytest.raises(ValueError):
            Asset(symbol="NIFTY", name="Nifty 50", lot_size=0)

    def test_asset_types(self):
        for t in AssetType:
            a = Asset(symbol=f"TEST_{t.value}", name="Test", asset_type=t)
            assert a.asset_type == t


class TestPortfolio:

    def test_create_portfolio(self):
        p = Portfolio(name="My Portfolio", initial_capital=1_000_000.0)
        assert p.name == "My Portfolio"
        assert p.initial_capital == 1_000_000.0
        assert p.currency == "INR"

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            Portfolio(name="  ")

    def test_negative_capital_rejected(self):
        with pytest.raises(ValueError):
            Portfolio(name="Bad", initial_capital=-100)

    def test_zero_capital_allowed(self):
        p = Portfolio(name="Paper", initial_capital=0)
        assert p.initial_capital == 0.0


class TestPosition:

    def test_create_long_position(self):
        pos = Position(portfolio_id=1, asset_id=1, quantity=10,
                       avg_entry_price=100.0, current_price=110.0)
        assert pos.side == Side.LONG
        assert pos.status == PositionStatus.OPEN
        assert pos.unrealized_pnl == 100.0  # 10 * (110 - 100)

    def test_short_position_pnl(self):
        pos = Position(portfolio_id=1, asset_id=1, quantity=10,
                       avg_entry_price=100.0, current_price=90.0,
                       side=Side.SHORT)
        assert pos.unrealized_pnl == 100.0  # -1 * 10 * (90 - 100)

    def test_short_position_loss(self):
        pos = Position(portfolio_id=1, asset_id=1, quantity=5,
                       avg_entry_price=100.0, current_price=120.0,
                       side=Side.SHORT)
        assert pos.unrealized_pnl == -100.0  # -1 * 5 * (120 - 100)

    def test_market_value(self):
        pos = Position(portfolio_id=1, asset_id=1, quantity=50,
                       current_price=200.0)
        assert pos.market_value == 10_000.0

    def test_negative_entry_price_rejected(self):
        with pytest.raises(ValueError):
            Position(portfolio_id=1, asset_id=1, avg_entry_price=-10)


class TestTrade:

    def test_create_buy_trade(self):
        t = Trade(portfolio_id=1, asset_id=1, side=Side.BUY,
                  quantity=100, price=50.0)
        assert t.is_simulated is True
        assert t.order_type == OrderType.MARKET
        assert t.total_cost == 5000.0

    def test_total_cost_with_fees(self):
        t = Trade(portfolio_id=1, asset_id=1, side=Side.BUY,
                  quantity=100, price=50.0, commission=20.0, slippage=5.0)
        assert t.total_cost == 5025.0

    def test_real_trading_rejected(self):
        with pytest.raises(ValueError, match="real trading is permanently disabled"):
            Trade(portfolio_id=1, asset_id=1, side=Side.BUY,
                  quantity=10, price=100.0, is_simulated=False)

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValueError):
            Trade(portfolio_id=1, asset_id=1, side=Side.BUY,
                  quantity=0, price=100.0)

    def test_negative_price_rejected(self):
        with pytest.raises(ValueError):
            Trade(portfolio_id=1, asset_id=1, side=Side.BUY,
                  quantity=10, price=-5.0)

    def test_negative_commission_rejected(self):
        with pytest.raises(ValueError):
            Trade(portfolio_id=1, asset_id=1, side=Side.BUY,
                  quantity=10, price=100.0, commission=-1.0)

    def test_all_order_types(self):
        for ot in OrderType:
            t = Trade(portfolio_id=1, asset_id=1, side=Side.BUY,
                      quantity=1, price=10.0, order_type=ot)
            assert t.order_type == ot
