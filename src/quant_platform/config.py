"""Configuration management — loads settings from environment variables."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class RunMode(str, Enum):
    LOCAL = "local"
    SERVER = "server"


class Settings(BaseSettings):
    model_config = {"env_prefix": "QP_", "env_file": ".env", "extra": "ignore"}

    db_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/quant_platform"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    log_level: str = "INFO"
    log_format: str = "json"

    real_trading: bool = False
    run_mode: RunMode = RunMode.LOCAL

    data_dir: str = Field(default_factory=lambda: str(Path(__file__).resolve().parent.parent.parent / "data"))

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    kill_switch_port: int = 8001
    kill_switch_heartbeat_interval: int = 5
    kill_switch_heartbeat_timeout: int = 15
    kill_switch_standalone: bool = False

    # LLM configuration — plug-and-play, swap via env var
    llm_provider: str = "claude"
    llm_model: str = "claude-sonnet-4-6"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # Telegram notifications
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Angel One SmartAPI — plug-and-play broker
    broker_adapter: str = "paper"
    angel_api_key: str | None = None
    angel_client_id: str | None = None
    angel_pin: str | None = None
    angel_totp_secret: str | None = None

    # Data provider — plug-and-play, swap via env var
    data_provider: str = "yfinance"

    # TradingView — plug-and-play research source
    research_source: str = "tradingview"
    tradingview_webhook_secret: str | None = None
    tradingview_username: str | None = None
    tradingview_password: str | None = None

    # Research engine settings
    research_interval_minutes: int = 60
    research_top_n_assets: int = 50
    research_source_mode: str = "both"

    # Trading settings
    paper_trading_days_required: int = 14
    max_positions: int = 20
    max_position_per_instrument: int = 3
    daily_loss_cap_pct: float = 0.05
    position_size_pct: float = 0.02

    # Promotion thresholds
    promotion_win_rate: float = 0.80
    promotion_min_trades: int = 20

    def ensure_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
