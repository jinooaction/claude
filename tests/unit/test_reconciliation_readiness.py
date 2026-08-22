from __future__ import annotations

from datetime import UTC, datetime, timedelta

from auto_invest.reconciliation.readiness import evaluate_resume_readiness

NOW = datetime(2026, 8, 22, 0, 0, tzinfo=UTC)


def test_resume_eligible_is_read_only_when_all_evidence_is_current() -> None:
    result = evaluate_resume_readiness(
        reconciliation_state="OK",
        reconciliation_finished_at_utc=(NOW - timedelta(hours=1)).isoformat(),
        now=NOW,
        halt_present=True,
        measurement_contract_id="sha256:abc",
        evidence_quality="VALID",
    )

    assert result.status == "RESUME_ELIGIBLE"
    assert result.orders_submitted == 0
    assert result.halt_cleared is False
    assert result.reasons == ()


def test_resume_readiness_fails_closed_for_mismatch_stale_or_missing_contract() -> None:
    mismatch = evaluate_resume_readiness(
        reconciliation_state="MISMATCH",
        reconciliation_finished_at_utc=NOW.isoformat(),
        now=NOW,
        halt_present=True,
        measurement_contract_id="sha256:abc",
        evidence_quality="VALID",
    )
    stale = evaluate_resume_readiness(
        reconciliation_state="OK",
        reconciliation_finished_at_utc=(NOW - timedelta(hours=49)).isoformat(),
        now=NOW,
        halt_present=True,
        measurement_contract_id=None,
        evidence_quality="BLOCKED",
    )

    assert mismatch.status == "BLOCKED"
    assert "reconciliation_not_ok" in mismatch.reasons
    assert stale.status == "STALE"
    assert "reconciliation_stale" in stale.reasons
    assert "measurement_contract_missing" in stale.reasons
