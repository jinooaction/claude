"""Tests for the LLM_CALL audit-log extension (T112)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import LlmCallPayload, PriceTableLoadedPayload


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    db.migrate(c)
    yield c
    c.close()


def test_llm_call_payload_validates():
    p = LlmCallPayload(
        model="claude-opus-4-7",
        decision_class="x",
        tokens_total=150,
        cost_usd="0.001",
        latency_ms=750,
        error_class=None,
    )
    assert p.event_type == "LLM_CALL"


def test_llm_call_payload_frozen():
    p = LlmCallPayload(
        model="m",
        decision_class=None,
        tokens_total=0,
        cost_usd=None,
        latency_ms=0,
        error_class=None,
    )
    with pytest.raises((TypeError, ValueError)):
        p.tokens_total = 999  # type: ignore[misc]


def test_llm_call_appended_to_audit_log(conn: sqlite3.Connection):
    audit.append(
        conn,
        LlmCallPayload(
            model="claude-opus-4-7",
            decision_class="news",
            tokens_total=200,
            cost_usd="0.002",
            latency_ms=1200,
            error_class=None,
        ),
        correlation_id="cid-1",
    )
    row = conn.execute(
        "SELECT event_type, correlation_id FROM audit_log"
    ).fetchone()
    assert row["event_type"] == "LLM_CALL"
    assert row["correlation_id"] == "cid-1"


def test_price_table_loaded_payload(conn: sqlite3.Connection):
    audit.append(
        conn,
        PriceTableLoadedPayload(path="config/llm_prices.toml", sha256="deadbeef"),
    )
    row = conn.execute(
        "SELECT event_type FROM audit_log WHERE event_type='PRICE_TABLE_LOADED'"
    ).fetchone()
    assert row is not None
