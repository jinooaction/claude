"""Spec 010 T006 — design 명령 mutex.

clean state 허용, stale RULE_DESIGN_REQUESTED 거부, exit_code 70, audit row.
"""

from __future__ import annotations

import json

import pytest

from auto_invest.design import mutex as design_mutex
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    RuleDesignCompletedPayload,
    RuleDesignRequestedPayload,
)


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _seed_requested(conn) -> int:
    return audit.append(
        conn,
        RuleDesignRequestedPayload(
            intent="test",
            requested_at_utc="2026-05-19T01:00:00.000Z",
            kis_balance_usd="100",
            kis_holdings=[],
            host="h",
        ),
    )


def _seed_completed(conn) -> int:
    return audit.append(
        conn,
        RuleDesignCompletedPayload(
            intent="test",
            interpretation={},
            generated_rules_toml="[caps]",
            model_id="claude-opus-4-7",
            tokens_input=1,
            tokens_output=1,
            cost_usd="0.001",
            retry_index=1,
        ),
    )


def test_clean_state_allows(conn) -> None:
    result = design_mutex.check_and_acquire(conn)
    assert result.allowed is True
    assert result.conflicting_event_id is None


def test_unpaired_requested_blocks(conn) -> None:
    seq = _seed_requested(conn)
    result = design_mutex.check_and_acquire(conn)
    assert result.allowed is False
    assert result.conflicting_event_id == seq
    assert result.exit_code == 70


def test_completed_pair_allows(conn) -> None:
    _seed_requested(conn)
    _seed_completed(conn)
    result = design_mutex.check_and_acquire(conn)
    assert result.allowed is True


def test_rejected_pair_allows(conn) -> None:
    from auto_invest.persistence.audit import RuleDesignRejectedPayload
    _seed_requested(conn)
    audit.append(
        conn,
        RuleDesignRejectedPayload(reason="claude_api_error", detail="timeout"),
    )
    result = design_mutex.check_and_acquire(conn)
    assert result.allowed is True


def test_rejection_records_audit_row(conn) -> None:
    seq = _seed_requested(conn)
    design_mutex.check_and_acquire(conn)

    rows = list(conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'RULE_DESIGN_REJECTED'"
    ))
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload_json"])
    assert payload["reason"] == "mutex_conflict"
    assert payload["conflicting_event_id"] == seq


def test_no_audit_when_allowed(conn) -> None:
    design_mutex.check_and_acquire(conn)
    rows = list(conn.execute(
        "SELECT COUNT(*) as n FROM audit_log "
        "WHERE event_type = 'RULE_DESIGN_REJECTED'"
    ))
    assert rows[0]["n"] == 0
