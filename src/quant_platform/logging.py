"""Structured JSON logging and audit trail."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from .config import get_settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event_type"):
            log_entry["event_type"] = record.event_type
        if hasattr(record, "agent"):
            log_entry["agent"] = record.agent
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry, default=str)


class AuditLogger:
    def __init__(self):
        self._logger = logging.getLogger("quant.audit")

    def log(self, action: str, source: str, details: dict[str, Any] | None = None) -> None:
        record = self._logger.makeRecord(
            name="quant.audit",
            level=logging.INFO,
            fn="",
            lno=0,
            msg=action,
            args=(),
            exc_info=None,
        )
        record.event_type = "audit"
        record.agent = source
        record.extra_data = details or {}
        self._logger.handle(record)


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger("quant")
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if settings.log_format == "json":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"quant.{name}")


audit = AuditLogger()
