"""Fail-closed revalidation for an exploration canary's first live fill."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

SCHEMA_VERSION = "1.0"
ENTRY_READY = "ENTRY_READY"
ENTRY_BLOCKED = "ENTRY_BLOCKED"
ACTIVE_LIVE_TRACK = "ACTIVE_LIVE_TRACK"


@dataclass(frozen=True)
class LiveEntryRevalidation:
    allowed: bool
    state: str
    fills_count: int | None
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_live_entry(
    profit_evidence: Any,
    hardened_canary: Any,
    live_performance: Any,
    *,
    evidence_age_hours: float | None,
    max_evidence_age_hours: float = 36.0,
    factory_evidence: Any = None,
    factory_evidence_age_hours: float | None = None,
    live_strategy_fingerprint: str | None = None,
) -> LiveEntryRevalidation:
    """Allow first exposure only under a current exploration or factory contract."""

    performance = live_performance if isinstance(live_performance, Mapping) else {}
    fills_count = _int_or_none(performance.get("fills_count"))
    if fills_count is None:
        return LiveEntryRevalidation(
            allowed=False,
            state=ENTRY_BLOCKED,
            fills_count=None,
            reasons=("strategy fills_count missing or invalid",),
            evidence={},
        )

    if fills_count > 0:
        return LiveEntryRevalidation(
            allowed=True,
            state=ACTIVE_LIVE_TRACK,
            fills_count=fills_count,
            reasons=(
                "strategy already has live fills; existing live risk gates remain authoritative",
            ),
            evidence={"fills_count": fills_count},
        )

    payload = profit_evidence if isinstance(profit_evidence, Mapping) else {}
    deployment = payload.get("deployment_match")
    deployment = deployment if isinstance(deployment, Mapping) else {}
    forward = deployment.get("forward")
    forward = forward if isinstance(forward, Mapping) else {}
    policy = deployment.get("entry_policy")
    policy = policy if isinstance(policy, Mapping) else {}

    n_obs = _int_or_none(forward.get("n_obs"))
    psr = _float_or_none(forward.get("psr_vs_benchmark"))
    min_obs = _int_or_none(policy.get("min_forward_obs")) or 40
    min_psr = _float_or_none(policy.get("min_forward_psr")) or 0.80
    canary_passed = (
        isinstance(hardened_canary, Mapping) and hardened_canary.get("verdict") == "PASS"
    )

    exploration_checks = {
        "historical_verdict": payload.get("historical_verdict") == "HOLDOUT_EDGE",
        "historical_passed": deployment.get("historical_passed") is True,
        "exploration_canary_ready": deployment.get("exploration_canary_ready") is True,
        "forward_observations": n_obs is not None and n_obs >= min_obs,
        "forward_psr": psr is not None and psr >= min_psr,
        "forward_calmar": forward.get("beats_benchmark_calmar") is True,
        "hardened_canary": canary_passed,
        "evidence_fresh": (
            evidence_age_hours is not None and 0.0 <= evidence_age_hours <= max_evidence_age_hours
        ),
    }
    factory = factory_evidence if isinstance(factory_evidence, Mapping) else {}
    factory_decision = factory.get("decision")
    factory_decision = factory_decision if isinstance(factory_decision, Mapping) else {}
    selected_fingerprint = factory_decision.get("selected_strategy_fingerprint")
    factory_checks = {
        "factory_verdict": factory_decision.get("verdict") == "FACTORY_EDGE",
        "factory_trials_complete": (
            _int_or_none(factory.get("candidate_count")) == 64
            and _int_or_none(factory.get("complete_trial_count")) == 64
        ),
        "factory_research_canary_eligible": (
            factory_decision.get("research_canary_eligible") is True
        ),
        "factory_strategy_fingerprint": (
            isinstance(selected_fingerprint, str)
            and selected_fingerprint != ""
            and selected_fingerprint == live_strategy_fingerprint
        ),
        "factory_hardened_canary": canary_passed,
        "factory_evidence_fresh": (
            factory_evidence_age_hours is not None
            and 0.0 <= factory_evidence_age_hours <= max_evidence_age_hours
        ),
    }
    exploration_ready = all(exploration_checks.values())
    factory_ready = bool(factory) and all(factory_checks.values())
    if exploration_ready or factory_ready:
        reasons: tuple[str, ...] = ()
    elif factory:
        reasons = tuple(key for key, passed in factory_checks.items() if not passed)
    else:
        reasons = tuple(key for key, passed in exploration_checks.items() if not passed)
    evidence = {
        "candidate_id": deployment.get("candidate_id"),
        "entry_source": (
            "strategy_factory" if factory_ready else "exploration" if exploration_ready else None
        ),
        "forward_n_obs": n_obs,
        "forward_psr": psr,
        "min_forward_obs": min_obs,
        "min_forward_psr": min_psr,
        "evidence_age_hours": evidence_age_hours,
        "max_evidence_age_hours": max_evidence_age_hours,
        "checks": exploration_checks,
        "factory_candidate_id": factory_decision.get("selected_candidate_id"),
        "factory_evidence_age_hours": factory_evidence_age_hours,
        "factory_checks": factory_checks,
    }
    return LiveEntryRevalidation(
        allowed=not reasons,
        state=ENTRY_READY if not reasons else ENTRY_BLOCKED,
        fills_count=0,
        reasons=reasons or ("all first-entry gates passed",),
        evidence=evidence,
    )


__all__ = [
    "ACTIVE_LIVE_TRACK",
    "ENTRY_BLOCKED",
    "ENTRY_READY",
    "LiveEntryRevalidation",
    "evaluate_live_entry",
]
