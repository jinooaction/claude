"""Spec 004 T004 — K4 추가-전용 판단 이벤트 페이로드."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    JudgmentAdvisoryAppliedPayload,
    JudgmentFallbackPayload,
)


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    db.migrate(c)
    yield c
    c.close()


def test_advisory_applied_payload_validates():
    p = JudgmentAdvisoryAppliedPayload(
        decision_class="volatility_assessment",
        advisory="size_down@0.80",
        applied_decision="size_down:0.5",
        canary_cohort=True,
    )
    assert p.event_type == "JUDGMENT_ADVISORY_APPLIED"
    assert p.canary_cohort is True


def test_fallback_payload_validates():
    p = JudgmentFallbackPayload(
        decision_class="news_screen", reason="timeout"
    )
    assert p.event_type == "JUDGMENT_FALLBACK"


def test_fallback_bad_reason_rejected():
    with pytest.raises((ValueError, TypeError)):
        JudgmentFallbackPayload(decision_class="x", reason="explosion")


def test_advisory_applied_appended(conn: sqlite3.Connection):
    seq = audit.append(
        conn,
        JudgmentAdvisoryAppliedPayload(
            decision_class="volatility_assessment",
            advisory="halt@0.95",
            applied_decision="skip",
            canary_cohort=False,
        ),
        rule_id="rule_dca",
        symbol="VOO",
        correlation_id="cid-1",
    )
    assert seq >= 1
    row = conn.execute(
        "SELECT event_type, correlation_id, rule_id, symbol FROM audit_log WHERE seq=?",
        (seq,),
    ).fetchone()
    assert row["event_type"] == "JUDGMENT_ADVISORY_APPLIED"
    assert row["correlation_id"] == "cid-1"
    assert row["rule_id"] == "rule_dca"
    assert row["symbol"] == "VOO"


def test_fallback_appended(conn: sqlite3.Connection):
    audit.append(
        conn,
        JudgmentFallbackPayload(
            decision_class="volatility_assessment", reason="circuit_open"
        ),
        correlation_id="cid-2",
    )
    row = conn.execute(
        "SELECT event_type FROM audit_log WHERE correlation_id='cid-2'"
    ).fetchone()
    assert row["event_type"] == "JUDGMENT_FALLBACK"


def test_existing_event_types_still_work(conn: sqlite3.Connection):
    """추가-전용: 기존 이벤트 타입이 깨지지 않는다."""
    from auto_invest.persistence.audit import LlmCallPayload

    audit.append(
        conn,
        LlmCallPayload(
            model="m", decision_class="x", tokens_total=1, cost_usd=None,
            latency_ms=1, error_class=None,
        ),
        correlation_id="cid-3",
    )
    row = conn.execute(
        "SELECT event_type FROM audit_log WHERE correlation_id='cid-3'"
    ).fetchone()
    assert row["event_type"] == "LLM_CALL"
