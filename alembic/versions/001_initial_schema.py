"""Initial schema — all 9 tables for the quant platform.

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(20), nullable=False, server_default="equity"),
        sa.Column("exchange", sa.String(20), nullable=False, server_default="NSE"),
        sa.Column("market_profile", sa.String(50), nullable=False, server_default="nse_equity"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("lot_size", sa.Integer, nullable=False, server_default="1"),
        sa.Column("tick_size", sa.Float, nullable=False, server_default="0.05"),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("market_cap_category", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "exchange", "asset_type", name="uq_asset_symbol_exchange_type"),
    )
    op.create_index("ix_asset_market_profile", "assets", ["market_profile"])
    op.create_index("ix_asset_exchange", "assets", ["exchange"])

    op.create_table(
        "ohlcv",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.DateTime, nullable=False),
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("adj_close", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=False, server_default="0"),
        sa.UniqueConstraint("asset_id", "date", name="uq_ohlcv_asset_date"),
    )
    op.create_index("ix_ohlcv_date", "ohlcv", ["date"])
    op.create_index("ix_ohlcv_asset_date", "ohlcv", ["asset_id", "date"])

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("initial_capital", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("parameters", sa.Text, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="discovered"),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("sharpe_ratio", sa.Float, nullable=True),
        sa.Column("max_drawdown", sa.Float, nullable=True),
        sa.Column("profit_factor", sa.Float, nullable=True),
        sa.Column("net_profit_after_fees", sa.Float, nullable=True),
        sa.Column("optimal_position_size", sa.Float, nullable=True),
        sa.Column("optimal_stop_loss", sa.Float, nullable=True),
        sa.Column("is_original", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("is_publishable", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("parent_strategy_ids", sa.Text, nullable=True),
        sa.Column("pine_script", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_strategy_status", "strategies", ["status"])
    op.create_index("ix_strategy_source", "strategies", ["source"])

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.Integer, sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("strategies.id"), nullable=True),
        sa.Column("quantity", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("avg_entry_price", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("current_price", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("side", sa.String(10), nullable=False, server_default="long"),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_position_status", "positions", ["status"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.Integer, sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("position_id", sa.Integer, sa.ForeignKey("positions.id"), nullable=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("strategies.id"), nullable=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("commission", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("slippage", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("order_type", sa.String(10), nullable=False, server_default="market"),
        sa.Column("is_simulated", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("executed_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("notes", sa.Text, server_default=""),
    )
    op.create_index("ix_trade_executed", "trades", ["executed_at"])
    op.create_index("ix_trade_strategy", "trades", ["strategy_id"])

    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("start_date", sa.DateTime, nullable=False),
        sa.Column("end_date", sa.DateTime, nullable=False),
        sa.Column("total_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("winning_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("losing_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("gross_profit", sa.Float, nullable=True),
        sa.Column("total_fees", sa.Float, server_default="0.0"),
        sa.Column("net_profit", sa.Float, nullable=True),
        sa.Column("sharpe_ratio", sa.Float, nullable=True),
        sa.Column("max_drawdown", sa.Float, nullable=True),
        sa.Column("profit_factor", sa.Float, nullable=True),
        sa.Column("avg_trade_pnl", sa.Float, nullable=True),
        sa.Column("parameters_used", sa.Text, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_backtest_strategy", "backtest_results", ["strategy_id"])

    op.create_table(
        "kill_switch_state",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("triggered_by", sa.String(50), nullable=True),
        sa.Column("triggered_at", sa.DateTime, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("last_heartbeat", sa.DateTime, nullable=True),
    )

    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("payload", sa.Text, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_event_type", "system_events", ["event_type"])
    op.create_index("ix_event_created", "system_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("system_events")
    op.drop_table("kill_switch_state")
    op.drop_table("backtest_results")
    op.drop_table("trades")
    op.drop_table("positions")
    op.drop_table("strategies")
    op.drop_table("portfolios")
    op.drop_table("ohlcv")
    op.drop_table("assets")
