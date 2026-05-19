"""Spec 010 T010 — `auto-invest design` 명령 동시 실행 방지.

audit_log에서 가장 최근 `RULE_DESIGN_REQUESTED`가 짝맞춤 `RULE_DESIGN_COMPLETED`
또는 `RULE_DESIGN_REJECTED` 없이 떠 있는지 1쿼리로 확인. 충돌 시
`RuleDesignRejectedPayload(reason="mutex_conflict")` 기록 + exit code 70 hint
리턴. spec 009 paper/mutex.py와 같은 구조 (R-D8).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from auto_invest.persistence import audit
from auto_invest.persistence.audit import RuleDesignRejectedPayload


@dataclass(frozen=True)
class DesignMutexResult:
    """`check_and_acquire`의 리턴값.

    - allowed=True: 시작 OK. 호출자가 후속 RULE_DESIGN_REQUESTED 기록.
    - allowed=False: 시작 거부. 호출자가 즉시 exit_code로 종료.
    """

    allowed: bool
    conflicting_event_id: int | None = None
    conflicting_session_started_at: str | None = None
    exit_code: int = 0


def _find_unpaired_design(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """가장 최근 RULE_DESIGN_REQUESTED 중 짝맞춤 COMPLETED/REJECTED 없는 row."""
    start_row = conn.execute(
        """
        SELECT seq, ts_utc FROM audit_log
        WHERE event_type = 'RULE_DESIGN_REQUESTED'
        ORDER BY seq DESC LIMIT 1
        """,
    ).fetchone()
    if start_row is None:
        return None
    pair = conn.execute(
        """
        SELECT seq FROM audit_log
        WHERE seq > ?
          AND event_type IN ('RULE_DESIGN_COMPLETED', 'RULE_DESIGN_REJECTED')
        LIMIT 1
        """,
        (start_row["seq"],),
    ).fetchone()
    if pair is not None:
        return None
    return start_row


def check_and_acquire(conn: sqlite3.Connection) -> DesignMutexResult:
    """design 명령 시작 가능성 검사.

    충돌 시 RULE_DESIGN_REJECTED audit row를 즉시 기록하고 exit_code=70 리턴.
    """
    unpaired = _find_unpaired_design(conn)
    if unpaired is None:
        return DesignMutexResult(allowed=True)

    detail = (
        f"다른 design 명령이 이미 실행 중입니다 "
        f"(seq={unpaired['seq']}, 시작 {unpaired['ts_utc']}). "
        "기존 명령 종료 후 다시 시도해주세요."
    )
    audit.append(
        conn,
        RuleDesignRejectedPayload(
            reason="mutex_conflict",
            detail=detail,
            conflicting_event_id=int(unpaired["seq"]),
        ),
    )
    return DesignMutexResult(
        allowed=False,
        conflicting_event_id=int(unpaired["seq"]),
        conflicting_session_started_at=str(unpaired["ts_utc"]),
        exit_code=70,
    )
