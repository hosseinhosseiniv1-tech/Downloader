"""Structured JSON logging helpers shared by bot, worker, and API helpers.

Design goals:
- UTC ISO-8601 timestamps everywhere.
- One JSON object per line (easy to ship to Railway logs, Loki, etc.).
- Correlation ID per job / per request surfaced in every log record.
- Never breaks if a value isn't JSON-serialisable.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

_RESERVED_LOGRECORD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render every log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Merge structured extras (anything not reserved by logging).
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            base[key] = _safe(value)

        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)

        try:
            return json.dumps(base, ensure_ascii=False, default=str)
        except Exception:  # pragma: no cover - defensive
            return json.dumps(
                {"ts": base["ts"], "level": base["level"], "msg": base["msg"], "error": "log_serialize_failed"}
            )


def _safe(value: Any) -> Any:
    """Best-effort JSON-safe conversion for arbitrary log extras."""
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configure root logging for the current process.

    Safe to call multiple times — subsequent calls are no-ops unless the
    level changes.
    """
    global _CONFIGURED
    resolved_level = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()

    if _CONFIGURED:
        logging.getLogger().setLevel(resolved_level)
        return

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(resolved_level)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Reduce noisy third-party loggers unless verbose is enabled.
    if os.environ.get("YDL_VERBOSE", "").lower() not in ("1", "true", "yes"):
        for noisy in ("urllib3", "requests", "yt_dlp", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger, ensuring global logging config is applied once."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)


def new_correlation_id(prefix: str = "job") -> str:
    """Generate a short correlation ID like ``job-1f3e9c2a``."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def elapsed_ms(started_at: float) -> int:
    """Helper to compute elapsed milliseconds from a ``time.monotonic()``."""
    return int((time.monotonic() - started_at) * 1000)