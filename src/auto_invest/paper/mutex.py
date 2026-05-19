"""Spec 009 T010 — paper-run · live-run 상호 배타 가드.

audit_log 1쿼리로 "가장 최근에 시작된 worker/paper 세션이 짝 없이 떠 있는지"
를 본다. SQLite advisory lock·파일 lock 없음 — 의존성 0, race window는
사람 손 속도(~100ms)로 무시 가능 (research.md R-P4).

호출 패턴:
    from auto_invest.paper import mutex
    result = mutex.check_and_acquire(conn, attempted_mode="paper")
    if not result.allowed:
        sys.exit(result.exit_code)
    # ... 정상 시작 시퀀스 (PAPER_RUN_STARTED 기록은 호출자 책임)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

from auto_invest.persistence import audit
from auto_invest.persistence.audit import PaperRunRejectedPayload

# 가장 최근에 짝 없이 시작된 세션을 표시하는 event_type 쌍.
# (시작 이벤트 → 그것에 매칭되는 종료 이벤트)
_LIFECYCLE_PAIRS = {
    "WORKER_STARTED": "WORKER_STOPPED",
    "PAPER_RUN_STARTED": "PAPER_RUN_STOPPED",
}


@dataclass(frozen=True)
class MutexResult:
    """`check_and_acquire`의 리턴값.

    - allowed=True: 시작 OK. 호출자가 PAPER_RUN_STARTED를 기록한다.
    - allowed=False: 시작 거부. 호출자가 즉시 exit_code로 종료한다.
      `conflicting_event_id`는 충돌 세션의 시작 row id.
      `PaperRunRejected` 페이로드는 이미 audit_log에 기록된 상태.
    """

    allowed: bool
    conflicting_event_id: int | None = None
    conflicting_event_type: str | None = None
    conflicting_session_started_at: str | None = None
    exit_code: int = 0  # allowed=True면 의미 없음


def _find_latest_unpaired_start(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """audit_log에서 가장 최근에 짝 없이 시작된 worker/paper 세션을 찾는다.

    알고리즘: WORKER_STARTED·PAPER_RUN_STARTED 중 가장 최근 row를 가져온다.
    그 row의 seq 이후로 같은 종류의 종료 이벤트가 있으면 짝맞음 → None 리턴.
    """
    # 가장 최근의 시작 이벤트
    cursor = conn.execute(
        """
        SELECT seq, event_type, ts_utc
        FROM audit_log
        WHERE event_type IN ('WORKER_STARTED', 'PAPER_RUN_STARTED')
        ORDER BY seq DESC
        LIMIT 1
        """
    )
    start_row = cursor.fetchone()
    if start_row is None:
        return None

    expected_stop = _LIFECYCLE_PAIRS[start_row["event_type"]]
    # 그 이후로 매칭되는 종료 이벤트가 있는가
    stop_cursor = conn.execute(
        """
        SELECT seq FROM audit_log
        WHERE seq > ? AND event_type = ?
        LIMIT 1
        """,
        (start_row["seq"], expected_stop),
    )
    if stop_cursor.fetchone() is not None:
        return None  # 짝맞음 — 충돌 아님
    return start_row


def check_and_acquire(
    conn: sqlite3.Connection,
    *,
    attempted_mode: Literal["paper", "live"],
) -> MutexResult:
    """paper-run 또는 live-run 시작 가능성을 검사한다.

    충돌 시 `PaperRunRejected` 페이로드를 audit_log에 즉시 기록하고
    `allowed=False`를 리턴. 호출자는 exit_code로 즉시 종료해야 한다.

    clean state면 `allowed=True` 리턴. 호출자가 후속으로
    `PAPER_RUN_STARTED` 또는 `WORKER_STARTED`를 기록한다.
    """
    unpaired = _find_latest_unpaired_start(conn)
    if unpaired is None:
        return MutexResult(allowed=True)

    detail = (
        f"{unpaired['event_type']} at {unpaired['ts_utc']} (seq={unpaired['seq']}) "
        f"is still running; finish it before starting {attempted_mode}-mode"
    )
    audit.append(
        conn,
        PaperRunRejectedPayload(
            attempted_mode=attempted_mode,
            reason="mutex_conflict",
            conflicting_event_id=int(unpaired["seq"]),
            conflicting_session_started_at=str(unpaired["ts_utc"]),
            detail=detail,
        ),
    )
    return MutexResult(
        allowed=False,
        conflicting_event_id=int(unpaired["seq"]),
        conflicting_event_type=str(unpaired["event_type"]),
        conflicting_session_started_at=str(unpaired["ts_utc"]),
        exit_code=70,
    )
