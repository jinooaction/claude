from __future__ import annotations

from pathlib import Path

import pytest

from auto_invest.persistence import audit, db
from auto_invest.reconciliation.readiness import ResumeReadiness
from auto_invest.reconciliation.recovery import recover_reconciliation_halt
from auto_invest.reconciliation.runner import ReconciliationOutcome
from auto_invest.worker.halt import read_halt, set_halt


def _outcome(state: str = "OK") -> ReconciliationOutcome:
    return ReconciliationOutcome(
        state=state,
        started_at_utc="2026-08-22T03:59:00.000Z",
        finished_at_utc="2026-08-22T04:00:00.000Z",
    )


def _readiness(*, halt_present: bool = True, status: str = "RESUME_ELIGIBLE") -> ResumeReadiness:
    return ResumeReadiness(
        status=status,
        reconciliation_state="OK",
        halt_present=halt_present,
        measurement_contract_id="sha256:valid",
        evidence_quality="VALID",
        reasons=(),
    )


def _connection(tmp_path: Path):
    conn = db.get_connection(tmp_path / "auto-invest.db")
    db.migrate(conn)
    return conn


def test_recovery_clears_only_reconciliation_halt_and_audits(tmp_path: Path) -> None:
    conn = _connection(tmp_path)
    halt_path = tmp_path / "halt.flag"
    initial = set_halt(halt_path, "reconciliation mismatch: 1 position(s)")

    report = recover_reconciliation_halt(
        conn,
        halt_path=halt_path,
        initial_halt=initial,
        outcome=_outcome(),
        readiness=_readiness(),
    )

    assert report.status == "RECOVERED"
    assert report.halt_cleared is True
    assert report.orders_submitted == 0
    assert not halt_path.exists()
    events = [row["event_type"] for row in audit.read_all(conn)]
    assert events == ["RECONCILIATION_HALT_RECOVERED", "HALT_CLEARED"]
    conn.close()


@pytest.mark.parametrize(
    "reason",
    ["operator maintenance", "circuit breaker: drawdown", "manual emergency stop"],
)
def test_recovery_preserves_non_reconciliation_halts(tmp_path: Path, reason: str) -> None:
    conn = _connection(tmp_path)
    halt_path = tmp_path / "halt.flag"
    initial = set_halt(halt_path, reason)

    report = recover_reconciliation_halt(
        conn,
        halt_path=halt_path,
        initial_halt=initial,
        outcome=_outcome(),
        readiness=_readiness(),
    )

    assert report.status == "BLOCKED"
    assert report.reasons == ("halt_reason_not_reconciliation",)
    assert read_halt(halt_path) == initial
    assert audit.read_all(conn) == []
    conn.close()


def test_recovery_refuses_a_halt_changed_after_reconciliation(tmp_path: Path) -> None:
    conn = _connection(tmp_path)
    halt_path = tmp_path / "halt.flag"
    initial = set_halt(halt_path, "reconciliation mismatch: 1 position(s)")
    replacement = set_halt(halt_path, "operator maintenance")

    report = recover_reconciliation_halt(
        conn,
        halt_path=halt_path,
        initial_halt=initial,
        outcome=_outcome(),
        readiness=_readiness(),
    )

    assert report.status == "BLOCKED"
    assert report.reasons == ("halt_changed_during_reconciliation",)
    assert read_halt(halt_path) == replacement
    conn.close()


def test_recovery_restores_halt_when_audit_write_fails(tmp_path: Path, monkeypatch) -> None:
    conn = _connection(tmp_path)
    halt_path = tmp_path / "halt.flag"
    initial = set_halt(halt_path, "reconciliation mismatch: 1 position(s)")

    def fail_append(*_args, **_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("auto_invest.reconciliation.recovery.audit.append", fail_append)
    with pytest.raises(RuntimeError, match="disk full"):
        recover_reconciliation_halt(
            conn,
            halt_path=halt_path,
            initial_halt=initial,
            outcome=_outcome(),
            readiness=_readiness(),
        )

    assert read_halt(halt_path) == initial
    assert audit.read_all(conn) == []
    conn.close()


def test_recovery_fails_closed_for_mismatch(tmp_path: Path) -> None:
    conn = _connection(tmp_path)
    halt_path = tmp_path / "halt.flag"
    initial = set_halt(halt_path, "reconciliation mismatch: 1 position(s)")

    report = recover_reconciliation_halt(
        conn,
        halt_path=halt_path,
        initial_halt=initial,
        outcome=_outcome("MISMATCH"),
        readiness=_readiness(status="BLOCKED"),
    )

    assert report.status == "BLOCKED"
    assert read_halt(halt_path) == initial
    conn.close()
