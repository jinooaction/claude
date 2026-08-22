"""Read-only readiness decision for releasing a reconciliation halt (spec 147)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ResumeReadiness:
    status: str
    reconciliation_state: str | None
    halt_present: bool
    measurement_contract_id: str | None
    evidence_quality: str
    reasons: tuple[str, ...]
    orders_submitted: int = 0
    halt_cleared: bool = False

    SCHEMA_VERSION = "1.0"

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "status": self.status,
            "reconciliation_state": self.reconciliation_state,
            "halt_present": self.halt_present,
            "measurement_contract_id": self.measurement_contract_id,
            "evidence_quality": self.evidence_quality,
            "reasons": list(self.reasons),
            "orders_submitted": self.orders_submitted,
            "halt_cleared": self.halt_cleared,
        }


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC)


def evaluate_resume_readiness(
    *,
    reconciliation_state: str | None,
    reconciliation_finished_at_utc: str | None,
    now: datetime,
    halt_present: bool,
    measurement_contract_id: str | None,
    evidence_quality: str,
    max_age_hours: float = 36.0,
) -> ResumeReadiness:
    reasons: list[str] = []
    finished = _parse_utc(reconciliation_finished_at_utc)
    stale = (
        finished is None or (now.astimezone(UTC) - finished).total_seconds() > max_age_hours * 3600
    )
    if stale:
        reasons.append("reconciliation_stale")
    if reconciliation_state != "OK":
        reasons.append("reconciliation_not_ok")
    if not measurement_contract_id:
        reasons.append("measurement_contract_missing")
    if evidence_quality != "VALID":
        reasons.append("measurement_quality_blocked")

    if stale:
        status = "STALE"
    elif reasons:
        status = "BLOCKED"
    elif halt_present:
        status = "RESUME_ELIGIBLE"
    else:
        status = "CLEAR"
    return ResumeReadiness(
        status=status,
        reconciliation_state=reconciliation_state,
        halt_present=halt_present,
        measurement_contract_id=measurement_contract_id,
        evidence_quality=evidence_quality,
        reasons=tuple(reasons),
    )
