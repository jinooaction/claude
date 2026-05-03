"""Logging configuration with secret redaction.

Per constitution principle V and FR-009: every value loaded as a
secret MUST be masked in any log record, error message, or report.
This module owns the secret registry and the filter that enforces it.

Design:
    * `register_secret(value)` is the single entry point that the
      `.env` loader calls for every value it reads.
    * `RedactionFilter` is installed once on the worker's stderr handler
      so every log record (message, args, extras, exception) is
      scrubbed before any formatter sees it.
    * `JsonFormatter` emits one JSON object per line; it deliberately
      consumes the redacted record produced by the filter and never
      re-formats `exc_info` directly.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from typing import Any

REDACTION_PLACEHOLDER = "***REDACTED***"
_MIN_SECRET_LENGTH = 4

_secrets: set[str] = set()

_STDLIB_LOGRECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


def register_secret(value: str) -> None:
    """Register a value to be redacted from every log record.

    Empty or trivially short values are ignored to avoid accidentally
    masking common substrings. Idempotent.
    """
    if not isinstance(value, str):
        return
    if len(value) < _MIN_SECRET_LENGTH:
        return
    _secrets.add(value)


def _redact(text: str) -> str:
    """Replace every registered secret in `text` with the placeholder."""
    if not _secrets or not text:
        return text
    redacted = text
    for secret in _secrets:
        if secret in redacted:
            redacted = redacted.replace(secret, REDACTION_PLACEHOLDER)
    return redacted


class RedactionFilter(logging.Filter):
    """Strip every registered secret from a log record in place.

    Applied upstream of every handler so that downstream formatters,
    custom handlers, and tracebacks all see the redacted form.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            formatted = record.getMessage()
        except Exception:
            formatted = str(record.msg)
        record.msg = _redact(formatted)
        record.args = ()

        if record.exc_info:
            etype, evalue, etb = record.exc_info
            if evalue is not None and evalue.args:
                evalue.args = tuple(_redact(a) if isinstance(a, str) else a for a in evalue.args)
            if not record.exc_text:
                record.exc_text = "".join(traceback.format_exception(*record.exc_info))
            record.exc_text = _redact(record.exc_text)

        if record.stack_info:
            record.stack_info = _redact(record.stack_info)

        for key, value in list(record.__dict__.items()):
            if key in _STDLIB_LOGRECORD_ATTRS:
                continue
            if isinstance(value, str):
                record.__dict__[key] = _redact(value)

        return True


class JsonFormatter(logging.Formatter):
    """Line-delimited JSON formatter."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STDLIB_LOGRECORD_ATTRS or key == "message":
                continue
            payload[key] = value
        if record.exc_info:
            etype = record.exc_info[0]
            evalue = record.exc_info[1]
            payload["exc_type"] = etype.__name__ if etype else None
            payload["exc_msg"] = str(evalue) if evalue is not None else None
            payload["traceback"] = record.exc_text or "".join(
                traceback.format_exception(*record.exc_info)
            )
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Install the JSON formatter + redaction filter on the root logger.

    Idempotent: previously installed handlers managed by this module are
    removed so repeat calls do not stack handlers.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_auto_invest_managed", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    handler._auto_invest_managed = True  # type: ignore[attr-defined]

    root.addHandler(handler)
    root.setLevel(level)
