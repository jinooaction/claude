"""Tests for `auto_invest.logging_config` — secret redaction (T009)."""

from __future__ import annotations

import io
import json
import logging

import pytest

from auto_invest import logging_config
from auto_invest.logging_config import (
    REDACTION_PLACEHOLDER,
    JsonFormatter,
    RedactionFilter,
    register_secret,
)


@pytest.fixture(autouse=True)
def _reset_secrets():
    logging_config._secrets.clear()
    yield
    logging_config._secrets.clear()


@pytest.fixture
def captured_logger():
    """Logger wired to in-memory stream with the production filter+formatter."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())

    logger = logging.getLogger("test_secret_masking")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    yield logger, buffer

    logger.handlers = []


def _records(buffer: io.StringIO) -> list[dict]:
    buffer.seek(0)
    return [json.loads(line) for line in buffer.read().splitlines() if line.strip()]


def test_register_secret_stores_value():
    register_secret("super-secret-key-1234")
    assert "super-secret-key-1234" in logging_config._secrets


def test_register_secret_ignores_empty_and_short():
    register_secret("")
    register_secret("abc")
    register_secret(None)  # type: ignore[arg-type]
    assert logging_config._secrets == set()


def test_register_secret_is_idempotent():
    register_secret("super-secret-key-1234")
    register_secret("super-secret-key-1234")
    assert len(logging_config._secrets) == 1


def test_redacts_log_message(captured_logger):
    logger, buffer = captured_logger
    register_secret("super-secret-key-1234")

    logger.info("auth using super-secret-key-1234 ok")

    [record] = _records(buffer)
    assert "super-secret-key-1234" not in record["msg"]
    assert REDACTION_PLACEHOLDER in record["msg"]


def test_redacts_log_args(captured_logger):
    logger, buffer = captured_logger
    register_secret("super-secret-key-1234")

    logger.info("token=%s", "super-secret-key-1234")

    [record] = _records(buffer)
    assert "super-secret-key-1234" not in record["msg"]
    assert REDACTION_PLACEHOLDER in record["msg"]


def test_redacts_exception_traceback_and_message(captured_logger):
    logger, buffer = captured_logger
    register_secret("super-secret-key-1234")

    try:
        raise ValueError("bad token: super-secret-key-1234")
    except ValueError:
        logger.exception("auth failed")

    [record] = _records(buffer)
    serialized = json.dumps(record)
    assert "super-secret-key-1234" not in serialized
    assert REDACTION_PLACEHOLDER in record["traceback"]
    assert REDACTION_PLACEHOLDER in record["exc_msg"]


def test_redacts_extra_fields(captured_logger):
    logger, buffer = captured_logger
    register_secret("super-secret-key-1234")

    logger.info("event", extra={"detail": "wrap super-secret-key-1234 here"})

    [record] = _records(buffer)
    assert "super-secret-key-1234" not in record["detail"]
    assert REDACTION_PLACEHOLDER in record["detail"]


def test_multiple_secrets_all_redacted(captured_logger):
    logger, buffer = captured_logger
    register_secret("alpha-secret-aaaa")
    register_secret("beta-secret-bbbb")

    logger.info("a=alpha-secret-aaaa b=beta-secret-bbbb")

    [record] = _records(buffer)
    assert "alpha-secret-aaaa" not in record["msg"]
    assert "beta-secret-bbbb" not in record["msg"]
    assert record["msg"].count(REDACTION_PLACEHOLDER) == 2


def test_no_secret_match_unchanged(captured_logger):
    logger, buffer = captured_logger
    register_secret("never-appears-9999")

    logger.info("nothing sensitive here")

    [record] = _records(buffer)
    assert record["msg"] == "nothing sensitive here"
    assert REDACTION_PLACEHOLDER not in record["msg"]


def test_redacts_stack_info(captured_logger):
    logger, buffer = captured_logger
    register_secret("super-secret-key-1234")

    logger.info(
        "x",
        extra={"_stack_simulated": "irrelevant"},
        stack_info=False,
    )
    # Inject stack_info manually to exercise the branch (logging.LogRecord
    # has no public way to set stack_info=True without an actual stack
    # capture, which won't contain our secret).
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="x",
        args=(),
        exc_info=None,
    )
    record.stack_info = "Stack with super-secret-key-1234 inside"
    RedactionFilter().filter(record)
    assert "super-secret-key-1234" not in record.stack_info
    assert REDACTION_PLACEHOLDER in record.stack_info
