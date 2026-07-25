"""Backtesting engine — Custom signal-based, fee-aware scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from ..database import get_db
from ..models import OHLCVORM, StrategyORM, BacktestResultORM, AssetORM
from ..plugins.broker import FeeSchedule
from ..logging import get_logger

logger = get_logger("backtesting")


class BacktestResult:
    def __init__(self):
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.gross_profit: float = 0.0
        self.total_fees: float = 0.0
        self.net_profit: float = 0.0
        self.max_drawdown: float = 0.0
        self.sharpe_ratio: float = 0.0
        self.profit_factor: float = 0.0
        self.avg_trade_pnl: float = 0.0
        self.equity_curve: list[float] = []
        self.trades: list[dict[str, Any]] = []

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def is_fee_profitable(self) -> bool:
        return self.net_profit > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "gross_profit": round(self.gross_profit, 2),
            "total_fees": round(self.total_fees, 2),
            "net_profit": round(self.net_profit, 2),
            "max_drawdown": round(self.max_drawdown, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "profit_factor": round(self.profit_factor, 4),
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "is_fee_profitable": self.is_fee_profitable,
        }


class BacktestEngine:

    def __init__(self, fee_schedule: FeeSchedule | None = None):
        self._fee_schedule = fee_schedule or FeeSchedule()

    def run_signal_backtest(
        self,
        prices: list[float],
        dates: list[datetime],
        entries: list[bool],
        exits: list[bool],
        initial_capital: float = 100000.0,
        position_size_pct: float = 1.0,
    ) -> BacktestResult:
        result = BacktestResult()
        capital = initial_capital
        position_qty = 0.0
        entry_price = 0.0
        peak_capital = capital
        max_dd = 0.0
        trade_pnls = []

        for i in range(len(prices)):
            if entries[i] and position_qty == 0:
                invest = capital * position_size_pct
                entry_fee = self._fee_schedule.calculate_total_fees(invest, "buy")
                position_qty = (invest - entry_fee) / prices[i]
                entry_price = prices[i]
                capital -= invest
                result.total_fees += entry_fee

            elif exits[i] and position_qty > 0:
                exit_value = position_qty * prices[i]
                exit_fee = self._fee_schedule.calculate_total_fees(exit_value, "sell")
                gross_pnl = (prices[i] - entry_price) * position_qty
                net_pnl = gross_pnl - exit_fee
                capital += exit_value - exit_fee
                result.total_fees += exit_fee

                trade_pnls.append(net_pnl)
                result.total_trades += 1
                if net_pnl > 0:
                    result.winning_trades += 1
                else:
                    result.losing_trades += 1
                result.gross_profit += gross_pnl

                result.trades.append({
                    "entry_date": dates[max(0, i - 1)].isoformat() if i > 0 else dates[0].isoformat(),
                    "exit_date": dates[i].isoformat(),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(prices[i], 2),
                    "quantity": round(position_qty, 4),
                    "gross_pnl": round(gross_pnl, 2),
                    "fees": round(exit_fee, 2),
                    "net_pnl": round(net_pnl, 2),
                })

                position_qty = 0.0
                entry_price = 0.0

            current_value = capital + (position_qty * prices[i] if position_qty > 0 else 0)
            result.equity_curve.append(round(current_value, 2))
            if current_value > peak_capital:
                peak_capital = current_value
            dd = (peak_capital - current_value) / peak_capital if peak_capital > 0 else 0
            if dd > max_dd:
                max_dd = dd

        result.max_drawdown = max_dd
        result.net_profit = sum(trade_pnls) if trade_pnls else 0.0

        if trade_pnls:
            result.avg_trade_pnl = sum(trade_pnls) / len(trade_pnls)
            gains = sum(p for p in trade_pnls if p > 0)
            losses = abs(sum(p for p in trade_pnls if p < 0))
            result.profit_factor = gains / losses if losses > 0 else float('inf')

            arr = np.array(trade_pnls)
            if arr.std() > 0:
                result.sharpe_ratio = float(arr.mean() / arr.std() * np.sqrt(252))

        return result

    def save_result(
        self,
        result: BacktestResult,
        strategy_id: int,
        asset_id: int,
        start_date: datetime,
        end_date: datetime,
        parameters_used: str = "{}",
    ) -> int:
        with get_db() as db:
            bt = BacktestResultORM(
                strategy_id=strategy_id,
                asset_id=asset_id,
                start_date=start_date,
                end_date=end_date,
                total_trades=result.total_trades,
                winning_trades=result.winning_trades,
                losing_trades=result.losing_trades,
                win_rate=result.win_rate,
                gross_profit=result.gross_profit,
                total_fees=result.total_fees,
                net_profit=result.net_profit,
                sharpe_ratio=result.sharpe_ratio,
                max_drawdown=result.max_drawdown,
                profit_factor=result.profit_factor,
                avg_trade_pnl=result.avg_trade_pnl,
                parameters_used=parameters_used,
            )
            db.add(bt)
            db.flush()
            return bt.id
