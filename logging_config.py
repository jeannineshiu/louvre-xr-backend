"""
ContextAR - Logging Configuration
Structured (JSON-lines) logging to stdout so a log aggregator (Railway,
Docker, etc.) can filter/query on fields directly instead of grepping text.

Usage:
    from logging_config import configure_logging
    configure_logging()  # call once, at process startup

    import logging
    logger = logging.getLogger(__name__)
    logger.info("ask_received", extra={"mode": "FULL_VOICE", "has_image": True})
"""

import json
import logging
import os
import sys
import time

# Fields present on every stdlib LogRecord — anything else in __dict__ came
# from a caller's `extra={...}` and should be merged into the JSON payload.
_RESERVED_RECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level":  record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_FIELDS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Idempotent: safe to call from multiple entry points (server.py, CLIs, tests)."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [_stdout_handler()]

    # Quiet noisy third-party loggers (HTTP client chatter from openai/httpx)
    # unless the operator explicitly asks for it.
    logging.getLogger("httpx").setLevel(os.environ.get("LOG_LEVEL_HTTPX", "WARNING"))
    logging.getLogger("httpcore").setLevel(os.environ.get("LOG_LEVEL_HTTPX", "WARNING"))


def _stdout_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    return handler
