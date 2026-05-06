"""Tests for `auto_invest.telemetry.store` (T131)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import LlmCallPayload
from auto_invest.telemetry.store import (
    TokenUsage,
    _utcnow_iso_ms,
    append_token_usage,
    integrity_check,
)


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    db.migrate(c)
    yield c
    c.close()


def _usage(correlation_id: str = "cid-1") -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class="news_screen",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=10,
        cache_write_tokens=20,
        cost_usd="0.001234",
        latency_ms=750,
        error_class=None,
        correlation_id=correlation_id,
        ts_utc=_utcnow_iso_ms(),
    )


def test_append_writes_one_row(conn: sqlite3.Connection):
    seq = append_token_usage(conn, _usage())
    assert seq == 1
    row = conn.execute("SELECT * FROM token_usage").fetchone()
    assert row["model"] == "claude-opus-4-7"
    assert row["decision_class"] == "news_screen"
    assert row["input_tokens"] == 100
    assert row["cost_usd"] == "0.001234"
    assert row["latency_ms"] == 750
    assert row["error_class"] is None


def test_append_only_update_rejected(conn: sqlite3.Connection):
    append_token_usage(conn, _usage())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE token_usage SET model='other' WHERE seq=1")


def test_append_only_delete_rejected(conn: sqlite3.Connection):
    append_token_usage(conn, _usage())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM token_usage WHERE seq=1")


def test_tokens_total_computed():
    u = _usage()
    assert u.tokens_total == 180


def test_integrity_check_clean(conn: sqlite3.Connection):
    u = _usage("cid-A")
    append_token_usage(conn, u)
    audit.append(
        conn,
        LlmCallPayload(
            model=u.model,
            decision_class=u.decision_class,
            tokens_total=u.tokens_total,
            cost_usd=u.cost_usd,
            latency_ms=u.latency_ms,
            error_class=None,
        ),
        correlation_id="cid-A",
    )
    assert integrity_check(conn) == []


def test_integrity_orphan_token_usage(conn: sqlite3.Connection):
    append_token_usage(conn, _usage("orphan-1"))
    mismatches = integrity_check(conn)
    assert len(mismatches) == 1
    assert mismatches[0].kind == "orphan_token_usage"
    assert mismatches[0].correlation_id == "orphan-1"


def test_integrity_orphan_llm_call(conn: sqlite3.Connection):
    audit.append(
        conn,
        LlmCallPayload(
            model="claude-opus-4-7",
            decision_class=None,
            tokens_total=0,
            cost_usd=None,
            latency_ms=0,
            error_class=None,
        ),
        correlation_id="orphan-2",
    )
    mismatches = integrity_check(conn)
    assert len(mismatches) == 1
    assert mismatches[0].kind == "orphan_llm_call"
    assert mismatches[0].correlation_id == "orphan-2"
