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

    llm_provider: str = "claude"
    llm_model: str = "claude-sonnet-4-6"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

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
