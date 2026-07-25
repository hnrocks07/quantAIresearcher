"""Configuration management — loads settings from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _default_db_path() -> str:
    return str(Path(__file__).resolve().parent.parent.parent / "data" / "trading.db")


class Settings(BaseSettings):
    model_config = {"env_prefix": "QP_", "env_file": ".env", "extra": "ignore"}

    db_url: str = Field(default_factory=lambda: f"sqlite:///{_default_db_path()}")
    log_level: str = "INFO"
    real_trading: bool = False
    data_dir: str = Field(default_factory=lambda: str(Path(__file__).resolve().parent.parent.parent / "data"))

    def ensure_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
