"""Execution-state guard for account-critical uncertainty.

This module is intentionally small and deny-by-default for new exposure. It
does not place, cancel, or recover orders; it only tells the router whether a
BUY may continue when critical account evidence is uncertain.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from auto_invest.broker.models import OrderRequest
from auto_invest.config.enums import Side
from auto_invest.risk.gates import GateDecision

ExecutionStatus = Literal["HEALTHY", "DEGRADED_SELL_ONLY", "HALTED"]


@dataclass(frozen=True)
class ExecutionStateReason:
    code: str
    detail: str


@dataclass(frozen=True)
class ExecutionState:
    status: ExecutionStatus
    reasons: tuple[ExecutionStateReason, ...] = ()

    @classmethod
    def healthy(cls) -> ExecutionState:
        return cls(status="HEALTHY")

    @classmethod
    def degraded(cls, reasons: Iterable[ExecutionStateReason]) -> ExecutionState:
        unique: dict[str, ExecutionStateReason] = {}
        for reason in reasons:
            unique.setdefault(reason.code, reason)
        if not unique:
            return cls.healthy()
        return cls(status="DEGRADED_SELL_ONLY", reasons=tuple(unique.values()))


def _submission_unknown_buy_reason(conn: sqlite3.Connection) -> ExecutionStateReason | None:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM orders
        WHERE side = 'BUY' AND state = 'SUBMISSION_UNKNOWN'
        """
    ).fetchone()
    count = int(row["n"]) if row is not None else 0
    if count <= 0:
        return None
    return ExecutionStateReason(
        code="submission_unknown_buy",
        detail=(
            f"{count} BUY order(s) have unclear broker submission status; "
            "block new BUY until order/execution lookup resolves them"
        ),
    )


def _parse_ts_utc(value: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _stale_pending_buy_reason(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    stale_after_seconds: int,
    exclude_correlation_ids: tuple[str, ...],
) -> ExecutionStateReason | None:
    clauses = ["o.side = 'BUY'", "o.state IN ('INTENT', 'SUBMITTING')"]
    params: list[object] = []
    if exclude_correlation_ids:
        placeholders = ",".join("?" for _ in exclude_correlation_ids)
        clauses.append(f"o.correlation_id NOT IN ({placeholders})")
        params.extend(exclude_correlation_ids)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT o.correlation_id, o.state, MAX(h.ts_utc) AS ts_utc
        FROM orders o
        LEFT JOIN order_state_history h
          ON h.order_correlation_id = o.correlation_id
         AND h.to_state = o.state
        WHERE {where}
        GROUP BY o.correlation_id, o.state
        """,
        params,
    ).fetchall()
    stale: list[str] = []
    now_utc = now.astimezone(UTC) if now.tzinfo is not None else now.replace(tzinfo=UTC)
    for row in rows:
        ts_raw = row["ts_utc"]
        if not ts_raw:
            continue
        ts = _parse_ts_utc(str(ts_raw))
        if ts is None:
            continue
        if (now_utc - ts).total_seconds() >= stale_after_seconds:
            stale.append(f"{row['correlation_id']}:{row['state']}")
    if not stale:
        return None
    return ExecutionStateReason(
        code="stale_pending_buy",
        detail=(
            f"{len(stale)} BUY order intent/submitting state(s) are stale; "
            "block new BUY until broker reconciliation proves the outcome"
        ),
    )


def _latest_reconciliation_reason(
    conn: sqlite3.Connection,
) -> ExecutionStateReason | None:
    row = conn.execute(
        """
        SELECT result
        FROM reconciliation_runs
        WHERE result IS NOT NULL
        ORDER BY seq DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None or row["result"] != "INCONCLUSIVE":
        return None
    return ExecutionStateReason(
        code="reconciliation_inconclusive",
        detail="latest reconciliation could not read broker positions or balance",
    )


def evaluate_execution_state(
    conn: sqlite3.Connection,
    *,
    runtime_reasons: Iterable[ExecutionStateReason] = (),
    now: datetime | None = None,
    stale_after_seconds: int = 60,
    exclude_correlation_ids: Iterable[str] = (),
) -> ExecutionState:
    """Evaluate persisted and worker-local blockers for new BUY exposure."""
    reasons: list[ExecutionStateReason] = []
    submission_unknown = _submission_unknown_buy_reason(conn)
    if submission_unknown is not None:
        reasons.append(submission_unknown)
    stale_pending = _stale_pending_buy_reason(
        conn,
        now=now or datetime.now(UTC),
        stale_after_seconds=stale_after_seconds,
        exclude_correlation_ids=tuple(exclude_correlation_ids),
    )
    if stale_pending is not None:
        reasons.append(stale_pending)
    reconciliation = _latest_reconciliation_reason(conn)
    if reconciliation is not None:
        reasons.append(reconciliation)
    reasons.extend(runtime_reasons)
    return ExecutionState.degraded(reasons)


def execution_state_gate(
    request: OrderRequest,
    *,
    state: ExecutionState,
) -> GateDecision:
    """Block exposure-increasing orders while preserving sell/recovery paths."""
    name = "execution_state_gate"
    if state.status == "HEALTHY":
        return GateDecision(allow=True, gate=name)
    reason_codes = [r.code for r in state.reasons]
    details = [r.detail for r in state.reasons]
    metadata = {
        "status": state.status,
        "reason_codes": reason_codes,
        "details": details,
    }
    if state.status == "DEGRADED_SELL_ONLY":
        if request.side is Side.SELL:
            return GateDecision(allow=True, gate=name, metadata=metadata)
        return GateDecision(
            allow=False,
            gate=name,
            reason="execution state is degraded; new BUY orders are blocked",
            metadata=metadata,
        )
    return GateDecision(
        allow=False,
        gate=name,
        reason="execution state is halted; orders are blocked",
        metadata=metadata,
    )


__all__ = [
    "ExecutionState",
    "ExecutionStateReason",
    "ExecutionStatus",
    "evaluate_execution_state",
    "execution_state_gate",
]
