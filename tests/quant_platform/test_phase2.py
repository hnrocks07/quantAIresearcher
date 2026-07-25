"""Phase 2 tests — backtesting engine, scoring, market profiles, strategies."""

import os
import json
import pytest
from datetime import datetime, timezone, timedelta

os.environ["QP_DB_URL"] = "sqlite://"

from quant_platform.database import get_engine, Base, get_db, reset_engine
from quant_platform.models import (
    AssetORM, OHLCVORM, StrategyORM, BacktestResultORM, StrategyStatus,
)
from quant_platform.data.backtesting import BacktestEngine, BacktestResult
from quant_platform.data.scoring import score_strategy, rank_strategies, StrategyScore
from quant_platform.plugins.broker import FeeSchedule
from quant_platform.market_profiles import load_profile, list_profiles, MarketProfile
from quant_platform.research.strategies import (
    sma_crossover, rsi_reversal, macd_signal, bollinger_breakout,
    mean_reversion, BUILTIN_STRATEGIES, PARAMETER_GRID,
)


@pytest.fixture(autouse=True)
def setup_db():
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield
    reset_engine()


def _create_asset(symbol="TEST.NS", name="Test Stock"):
    with get_db() as db:
        a = AssetORM(symbol=symbol, name=name, asset_type="equity", exchange="NSE", market_profile="nse_equity")
        db.add(a)
        db.flush()
        return a.id


def _create_ohlcv(asset_id, days=200, base_price=100.0):
    with get_db() as db:
        for i in range(days):
            dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
            import math
            price = base_price + 20 * math.sin(i * 0.1) + i * 0.05
            db.add(OHLCVORM(
                asset_id=asset_id, date=dt,
                open=price - 1, high=price + 2, low=price - 2,
                close=price, adj_close=price, volume=100000,
            ))
        db.flush()


def _create_strategy(name="test_strategy"):
    with get_db() as db:
        s = StrategyORM(
            name=name, description="test", source="test",
            status=StrategyStatus.BACKTESTING.value,
            parameters="{}",
        )
        db.add(s)
        db.flush()
        return s.id


# --- BacktestResult ---

class TestBacktestResult:
    def test_empty_result(self):
        r = BacktestResult()
        assert r.win_rate == 0.0
        assert r.is_fee_profitable is False
        assert r.total_trades == 0

    def test_to_dict(self):
        r = BacktestResult()
        r.total_trades = 10
        r.winning_trades = 7
        r.net_profit = 5000.0
        d = r.to_dict()
        assert d["win_rate"] == 0.7
        assert d["is_fee_profitable"] is True


# --- BacktestEngine ---

class TestBacktestEngine:
    def test_no_signals(self):
        engine = BacktestEngine()
        prices = [100.0] * 50
        dates = [datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(50)]
        entries = [False] * 50
        exits = [False] * 50
        result = engine.run_signal_backtest(prices, dates, entries, exits)
        assert result.total_trades == 0

    def test_single_winning_trade(self):
        engine = BacktestEngine()
        prices = [100.0] * 10 + [110.0] * 10
        dates = [datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(20)]
        entries = [False] * 20
        exits = [False] * 20
        entries[0] = True
        exits[15] = True
        result = engine.run_signal_backtest(prices, dates, entries, exits)
        assert result.total_trades == 1
        assert result.winning_trades == 1
        assert result.net_profit > 0

    def test_single_losing_trade(self):
        engine = BacktestEngine()
        prices = [100.0] * 10 + [90.0] * 10
        dates = [datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(20)]
        entries = [False] * 20
        exits = [False] * 20
        entries[0] = True
        exits[15] = True
        result = engine.run_signal_backtest(prices, dates, entries, exits)
        assert result.total_trades == 1
        assert result.losing_trades == 1
        assert result.net_profit < 0

    def test_fee_impact(self):
        fee = FeeSchedule(commission_pct=0.01)
        engine = BacktestEngine(fee_schedule=fee)
        prices = [100.0] * 10 + [101.0] * 10
        dates = [datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(20)]
        entries = [False] * 20
        exits = [False] * 20
        entries[0] = True
        exits[15] = True
        result = engine.run_signal_backtest(prices, dates, entries, exits)
        assert result.total_fees > 0

    def test_multiple_trades(self):
        engine = BacktestEngine()
        prices = ([100.0] * 5 + [110.0] * 5) * 4
        dates = [datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(40)]
        entries = [False] * 40
        exits = [False] * 40
        entries[0] = True; exits[7] = True
        entries[10] = True; exits[17] = True
        result = engine.run_signal_backtest(prices, dates, entries, exits)
        assert result.total_trades == 2

    def test_equity_curve(self):
        engine = BacktestEngine()
        prices = [100.0] * 20
        dates = [datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(20)]
        entries = [False] * 20
        exits = [False] * 20
        result = engine.run_signal_backtest(prices, dates, entries, exits)
        assert len(result.equity_curve) == 20

    def test_save_result(self):
        asset_id = _create_asset()
        strategy_id = _create_strategy()
        engine = BacktestEngine()
        result = BacktestResult()
        result.total_trades = 5
        result.winning_trades = 3
        result.net_profit = 1000.0
        result.sharpe_ratio = 1.5
        bt_id = engine.save_result(
            result, strategy_id, asset_id,
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2021, 1, 1, tzinfo=timezone.utc),
        )
        assert bt_id > 0
        with get_db() as db:
            saved = db.query(BacktestResultORM).filter(BacktestResultORM.id == bt_id).first()
            assert saved.total_trades == 5
            assert saved.net_profit == 1000.0


# --- Scoring ---

class TestScoring:
    def test_score_nonexistent(self):
        assert score_strategy(9999) is None

    def test_score_no_backtests(self):
        sid = _create_strategy("no_bt")
        score = score_strategy(sid)
        assert score is not None
        assert score.composite_score == 0.0

    def test_score_with_backtests(self):
        asset_id = _create_asset("SCORE.NS", "Score Test")
        sid = _create_strategy("scored_strat")
        with get_db() as db:
            db.add(BacktestResultORM(
                strategy_id=sid, asset_id=asset_id,
                start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
                total_trades=20, winning_trades=16, losing_trades=4,
                win_rate=0.8, gross_profit=10000, total_fees=500,
                net_profit=9500, sharpe_ratio=2.0, max_drawdown=0.05,
                profit_factor=3.0, avg_trade_pnl=475,
            ))
            db.flush()
        score = score_strategy(sid)
        assert score.win_rate == 0.8
        assert score.is_fee_profitable is True
        assert score.composite_score > 0

    def test_rank_strategies(self):
        a = _create_asset("RANK.NS", "Rank Test")
        s1 = _create_strategy("rank_good")
        s2 = _create_strategy("rank_bad")
        with get_db() as db:
            db.add(BacktestResultORM(
                strategy_id=s1, asset_id=a,
                start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
                total_trades=10, winning_trades=8, losing_trades=2,
                win_rate=0.8, gross_profit=5000, total_fees=100,
                net_profit=4900, sharpe_ratio=2.5, max_drawdown=0.03,
                profit_factor=4.0, avg_trade_pnl=490,
            ))
            db.add(BacktestResultORM(
                strategy_id=s2, asset_id=a,
                start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
                total_trades=10, winning_trades=3, losing_trades=7,
                win_rate=0.3, gross_profit=-2000, total_fees=500,
                net_profit=-2500, sharpe_ratio=-0.5, max_drawdown=0.25,
                profit_factor=0.3, avg_trade_pnl=-250,
            ))
            db.flush()
        rankings = rank_strategies([s1, s2])
        assert len(rankings) == 2
        assert rankings[0].rank == 1
        assert rankings[0].composite_score >= rankings[1].composite_score


# --- Market Profiles ---

class TestMarketProfiles:
    def test_list_profiles(self):
        profiles = list_profiles()
        assert "nse_equity" in profiles
        assert "crypto" in profiles

    def test_load_nse(self):
        p = load_profile("nse_equity")
        assert p.name == "nse_equity"
        assert p.currency == "INR"
        assert p.exchange == "NSE"
        assert p.history_years == 20
        assert len(p.instruments) >= 3

    def test_load_crypto(self):
        p = load_profile("crypto")
        assert p.currency == "USD"
        assert p.exchange == "CRYPTO"
        assert len(p.instruments) >= 10

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_profile("nonexistent_market")

    def test_from_dict(self):
        d = {"name": "test", "display_name": "Test", "data_provider": "yf", "currency": "USD", "exchange": "TEST"}
        p = MarketProfile.from_dict(d)
        assert p.name == "test"


# --- Strategy Signal Generators ---

class TestStrategies:
    def _make_prices(self, n=300):
        import math
        return [100 + 20 * math.sin(i * 0.05) + i * 0.02 for i in range(n)]

    def test_sma_crossover(self):
        s = sma_crossover(self._make_prices(), fast=10, slow=30)
        assert len(s.entries) == 300
        assert any(s.entries) or any(s.exits)

    def test_rsi_reversal(self):
        s = rsi_reversal(self._make_prices())
        assert len(s.entries) == 300

    def test_macd_signal(self):
        s = macd_signal(self._make_prices())
        assert len(s.entries) == 300

    def test_bollinger_breakout(self):
        s = bollinger_breakout(self._make_prices())
        assert len(s.entries) == 300

    def test_mean_reversion(self):
        s = mean_reversion(self._make_prices())
        assert len(s.entries) == 300

    def test_short_data_no_crash(self):
        for func in BUILTIN_STRATEGIES.values():
            s = func([100.0] * 5)
            assert len(s.entries) == 5

    def test_all_strategies_registered(self):
        assert len(BUILTIN_STRATEGIES) == 5
        assert len(PARAMETER_GRID) == 5

    def test_parameter_grid_compatible(self):
        prices = self._make_prices()
        for name, func in BUILTIN_STRATEGIES.items():
            for params in PARAMETER_GRID[name]:
                s = func(prices, **params)
                assert len(s.entries) == len(prices)
