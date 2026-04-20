"""
Structured JSON logger for Lambda.
CloudWatch Insights can parse JSON log lines automatically.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record for easy CloudWatch querying."""

    _SKIP = frozenset(
        {
            "args", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message",
            "module", "msecs", "msg", "name", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "thread",
            "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }
        # Attach any extra fields passed via `extra={...}`
        for key, val in record.__dict__.items():
            if key not in self._SKIP:
                payload[key] = val

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    return logger
