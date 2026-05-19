"""Spec 009 T006 — paper-run · live-run 상호 배타 가드 (FR-015, SC-007).

paper-run 시작 시 audit_log에 stop 짝 없는 `WORKER_STARTED` 또는
`PAPER_RUN_STARTED` row가 있으면 mutex 충돌로 시작을 거부한다. 거부 시:

  - `PaperRunRejectedPayload(reason="mutex_conflict")` audit_log 기록.
  - 호출자에게 "거부됨 + exit code 70 hint" 전달.

clean state(stop 짝이 모두 매칭됨)에서는 충돌 없음을 리턴하여 호출자가
`PAPER_RUN_STARTED`를 기록하고 정상 진행하도록 한다.

대응 모듈: `src/auto_invest/paper/mutex.py`.
"""

from __future__ import annotations

import pytest

from auto_invest.paper import mutex as paper_mutex
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    PaperRunStartedPayload,
    PaperRunStoppedPayload,
    WorkerStartedPayload,
    WorkerStoppedPayload,
)


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "test.db")
    db.migrate(c)
    yield c
    c.close()


def _seed_worker_started(conn) -> int:
    return audit.append(
        conn,
        WorkerStartedPayload(pid=999, config_path="/etc/auto-invest/rules.toml"),
    )


def _seed_paper_started(conn) -> int:
    return audit.append(
        conn,
        PaperRunStartedPayload(
            pid=888,
            config_path="/etc/auto-invest/rules.toml",
            ruleset_sha256="a" * 64,
            started_at_utc="2026-05-19T01:00:00.000Z",
            host="vultr-paper-1",
        ),
    )


def test_clean_state_allows_paper_start(conn) -> None:
    """audit_log가 비어 있으면 mutex 충돌 없음 → 시작 허용."""
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is True
    assert result.conflicting_event_id is None


def test_live_worker_running_blocks_paper(conn) -> None:
    """stop 짝 없는 WORKER_STARTED가 있으면 paper-run 시작 거부."""
    started_id = _seed_worker_started(conn)
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is False
    assert result.conflicting_event_id == started_id
    assert result.exit_code == 70


def test_live_worker_stopped_allows_paper(conn) -> None:
    """WORKER_STARTED와 짝맞는 WORKER_STOPPED가 있으면 충돌 없음."""
    _seed_worker_started(conn)
    audit.append(conn, WorkerStoppedPayload(reason="normal_shutdown"))
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is True


def test_existing_paper_run_blocks_new_paper(conn) -> None:
    """stop 짝 없는 PAPER_RUN_STARTED가 있어도 새 paper-run 시작 거부."""
    started_id = _seed_paper_started(conn)
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is False
    assert result.conflicting_event_id == started_id


def test_existing_paper_run_stopped_allows_new(conn) -> None:
    started_id = _seed_paper_started(conn)
    audit.append(
        conn,
        PaperRunStoppedPayload(
            reason="signal_received",
            stopped_at_utc="2026-05-19T14:00:00.000Z",
            session_started_event_id=started_id,
        ),
    )
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is True


def test_paper_running_blocks_live(conn) -> None:
    """역방향도 동일 — paper가 떠 있으면 live 시작 거부."""
    started_id = _seed_paper_started(conn)
    result = paper_mutex.check_and_acquire(conn, attempted_mode="live")
    assert result.allowed is False
    assert result.conflicting_event_id == started_id
    assert result.exit_code == 70


def test_rejection_records_audit_event(conn) -> None:
    """충돌 시 audit_log에 PAPER_RUN_REJECTED row 추가."""
    started_id = _seed_worker_started(conn)
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is False

    rows = list(conn.execute(
        "SELECT event_type, payload_json FROM audit_log "
        "WHERE event_type = 'PAPER_RUN_REJECTED'"
    ))
    assert len(rows) == 1
    import json
    payload = json.loads(rows[0]["payload_json"])
    assert payload["attempted_mode"] == "paper"
    assert payload["reason"] == "mutex_conflict"
    assert payload["conflicting_event_id"] == started_id


def test_no_rejection_audit_when_allowed(conn) -> None:
    """clean state에서는 PAPER_RUN_REJECTED row 기록 안 함."""
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is True
    rows = list(conn.execute(
        "SELECT COUNT(*) as n FROM audit_log WHERE event_type = 'PAPER_RUN_REJECTED'"
    ))
    assert rows[0]["n"] == 0


def test_multiple_lifecycles_correctly_paired(conn) -> None:
    """과거에 시작/종료가 여러 번 있었어도 가장 최근만 본다."""
    _seed_worker_started(conn)
    audit.append(conn, WorkerStoppedPayload(reason="normal_shutdown"))
    s2 = _seed_paper_started(conn)
    audit.append(
        conn,
        PaperRunStoppedPayload(
            reason="signal_received",
            stopped_at_utc="2026-05-19T14:00:00.000Z",
            session_started_event_id=s2,
        ),
    )
    s3 = _seed_worker_started(conn)  # 다시 live 시작
    # 가장 최근 시작이 짝 없으므로 충돌
    result = paper_mutex.check_and_acquire(conn, attempted_mode="paper")
    assert result.allowed is False
    assert result.conflicting_event_id == s3
