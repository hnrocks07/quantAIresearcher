"""Unit tests for quant platform configuration."""

import os

import pytest


def test_settings_defaults():
    os.environ.pop("QP_DB_URL", None)
    os.environ.pop("QP_REAL_TRADING", None)
    from quant_platform.config import Settings
    s = Settings()
    assert "sqlite" in s.db_url
    assert s.real_trading is False
    assert s.log_level == "INFO"


def test_real_trading_default_false():
    from quant_platform.config import Settings
    s = Settings()
    assert s.real_trading is False


def test_db_url_override(monkeypatch):
    monkeypatch.setenv("QP_DB_URL", "sqlite:///custom.db")
    from quant_platform.config import Settings
    s = Settings()
    assert s.db_url == "sqlite:///custom.db"
