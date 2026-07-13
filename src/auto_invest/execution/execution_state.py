"""Execution-state guard for account-critical uncertainty.

This module is intentionally small and deny-by-default for new exposure. It
does not place, cancel, or recover orders; it only tells the router whether a
BUY may continue when critical account evidence is uncertain.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
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
) -> ExecutionState:
    """Evaluate persisted and worker-local blockers for new BUY exposure."""
    reasons: list[ExecutionStateReason] = []
    submission_unknown = _submission_unknown_buy_reason(conn)
    if submission_unknown is not None:
        reasons.append(submission_unknown)
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
