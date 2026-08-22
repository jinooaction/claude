"""Fail-closed release of a halt caused specifically by reconciliation drift."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.persistence import audit
from auto_invest.persistence.audit import (
    HaltClearedPayload,
    ReconciliationHaltRecoveredPayload,
)
from auto_invest.reconciliation.readiness import ResumeReadiness
from auto_invest.reconciliation.runner import (
    RECONCILIATION_HALT_PREFIX,
    ReconciliationOutcome,
)
from auto_invest.worker.halt import HaltState, clear_halt, read_halt


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class ReconciliationRecoveryReport:
    status: str
    observed_at_utc: str
    halt_present_before: bool
    halt_present_after: bool
    halt_reason_before: str | None
    reconciliation_state: str
    measurement_contract_id: str | None
    evidence_quality: str
    halt_cleared: bool
    reasons: tuple[str, ...]
    orders_submitted: int = 0

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "status": self.status,
            "observed_at_utc": self.observed_at_utc,
            "halt_present_before": self.halt_present_before,
            "halt_present_after": self.halt_present_after,
            "halt_reason_before": self.halt_reason_before,
            "reconciliation_state": self.reconciliation_state,
            "measurement_contract_id": self.measurement_contract_id,
            "evidence_quality": self.evidence_quality,
            "halt_cleared": self.halt_cleared,
            "orders_submitted": self.orders_submitted,
            "reasons": list(self.reasons),
        }


def _report(
    *,
    status: str,
    initial_halt: HaltState | None,
    halt_path: Path,
    outcome: ReconciliationOutcome,
    readiness: ResumeReadiness,
    halt_cleared: bool = False,
    reasons: tuple[str, ...] = (),
) -> ReconciliationRecoveryReport:
    return ReconciliationRecoveryReport(
        status=status,
        observed_at_utc=_utcnow_iso_ms(),
        halt_present_before=initial_halt is not None,
        halt_present_after=halt_path.exists(),
        halt_reason_before=None if initial_halt is None else initial_halt.reason,
        reconciliation_state=outcome.state,
        measurement_contract_id=readiness.measurement_contract_id,
        evidence_quality=readiness.evidence_quality,
        halt_cleared=halt_cleared,
        reasons=reasons,
    )


def recover_reconciliation_halt(
    conn: sqlite3.Connection,
    *,
    halt_path: Path,
    initial_halt: HaltState | None,
    outcome: ReconciliationOutcome,
    readiness: ResumeReadiness,
) -> ReconciliationRecoveryReport:
    """Release only the unchanged reconciliation halt backed by fresh valid evidence."""
    if outcome.state == "INCONCLUSIVE":
        return _report(
            status="INCONCLUSIVE",
            initial_halt=initial_halt,
            halt_path=halt_path,
            outcome=outcome,
            readiness=readiness,
            reasons=("reconciliation_inconclusive",),
        )
    if outcome.state != "OK":
        return _report(
            status="BLOCKED",
            initial_halt=initial_halt,
            halt_path=halt_path,
            outcome=outcome,
            readiness=readiness,
            reasons=("reconciliation_not_ok",),
        )
    if initial_halt is None:
        current_halt = read_halt(halt_path)
        reasons = () if current_halt is None else ("halt_changed_during_reconciliation",)
        return _report(
            status="CLEAR" if current_halt is None else "BLOCKED",
            initial_halt=initial_halt,
            halt_path=halt_path,
            outcome=outcome,
            readiness=readiness,
            reasons=reasons,
        )
    if not initial_halt.reason.startswith(RECONCILIATION_HALT_PREFIX):
        return _report(
            status="BLOCKED",
            initial_halt=initial_halt,
            halt_path=halt_path,
            outcome=outcome,
            readiness=readiness,
            reasons=("halt_reason_not_reconciliation",),
        )
    if readiness.status != "RESUME_ELIGIBLE" or not readiness.measurement_contract_id:
        return _report(
            status="BLOCKED",
            initial_halt=initial_halt,
            halt_path=halt_path,
            outcome=outcome,
            readiness=readiness,
            reasons=readiness.reasons or ("resume_not_eligible",),
        )

    cleared = False
    conn.execute("BEGIN IMMEDIATE")
    try:
        current_halt = read_halt(halt_path)
        if current_halt != initial_halt:
            conn.execute("ROLLBACK")
            return _report(
                status="BLOCKED",
                initial_halt=initial_halt,
                halt_path=halt_path,
                outcome=outcome,
                readiness=readiness,
                reasons=("halt_changed_during_reconciliation",),
            )
        cleared = clear_halt(halt_path)
        if not cleared:
            raise RuntimeError("halt disappeared before recovery")
        audit.append(
            conn,
            ReconciliationHaltRecoveredPayload(
                previous_halt_reason=initial_halt.reason,
                reconciliation_finished_at_utc=outcome.finished_at_utc,
                measurement_contract_id=readiness.measurement_contract_id,
            ),
        )
        audit.append(conn, HaltClearedPayload(cleared_by="reconciliation-recovery"))
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        if cleared and not halt_path.exists():
            halt_path.parent.mkdir(parents=True, exist_ok=True)
            halt_path.write_text(initial_halt.model_dump_json(), encoding="utf-8")
        raise

    return _report(
        status="RECOVERED",
        initial_halt=initial_halt,
        halt_path=halt_path,
        outcome=outcome,
        readiness=readiness,
        halt_cleared=True,
    )
