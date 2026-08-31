"""Typed, independently recomputed evidence for the bounded 10% live canary.

This contract proves that a preregistered exact deployment is stable enough to
exercise real order/fill/reconciliation plumbing.  It deliberately does not
claim benchmark alpha and can never authorize capital above ladder rung 1.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from auto_invest.analytics.backtest_overfitting import probabilistic_sharpe
from auto_invest.analytics.profit_evidence_engine import apply_annual_cost_drag
from auto_invest.analytics.risk_managed_beta import LegStats, summarize

SCHEMA_VERSION = "1.0"
ROLE = "operational_canary_entry"
ROUTE = "historical-operational-canary-v1"
CANDIDATE_ID = "globalfixed-ensemble-3-6-9-12"
READY = "OPERATIONAL_CANARY_READY"
BLOCKED = "BLOCKED"
MAX_EVIDENCE_AGE_HOURS = 36.0

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class OperationalCanaryAssessment:
    eligible: bool
    alpha_confirmed: bool
    capital_fraction: float
    max_rung: int
    candidate_id: str | None
    strategy_fingerprint: str | None
    reasons: tuple[str, ...]
    checks: dict[str, bool]
    recomputed: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}


def _performance(stats: LegStats) -> dict[str, Any]:
    return {
        "n_months": stats.n_months,
        "cagr_pct": round(stats.cagr_pct, 6),
        "sharpe": round(stats.sharpe, 6),
        "max_drawdown_pct": round(stats.max_dd_pct, 6),
        "calmar": None if stats.calmar is None else round(stats.calmar, 6),
    }


def _data_fingerprint(
    *,
    months: Sequence[str],
    candidate_factors: Sequence[float],
    benchmark_factors: Sequence[float],
    development_months: int,
    annual_cost_bps: int,
) -> str:
    payload = {
        "months": list(months),
        "candidate_monthly_factors": [round(float(value), 12) for value in candidate_factors],
        "benchmark_monthly_factors": [round(float(value), 12) for value in benchmark_factors],
        "development_months": development_months,
        "annual_cost_bps": annual_cost_bps,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _active_psr(candidate: Sequence[float], benchmark: Sequence[float]) -> float | None:
    active_returns = [
        (float(candidate_factor) - 1.0) - (float(benchmark_factor) - 1.0)
        for candidate_factor, benchmark_factor in zip(candidate, benchmark, strict=True)
    ]
    value = probabilistic_sharpe(active_returns)
    return None if value is None else round(float(value), 12)


def _cost_sensitivity(
    candidate_base_net: Sequence[float],
    benchmark: Sequence[float],
    *,
    base_annual_bps: int,
) -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {}
    for annual_bps in (100, 150):
        extra = max(0, annual_bps - base_annual_bps)
        stressed = apply_annual_cost_drag(
            candidate_base_net,
            annual_cost_bps=extra,
        )
        stats = summarize(stressed)
        active = [
            (candidate_factor - 1.0) - (float(benchmark_factor) - 1.0)
            for candidate_factor, benchmark_factor in zip(stressed, benchmark, strict=True)
        ]
        result[str(annual_bps)] = {
            "candidate_sharpe": round(stats.sharpe, 6),
            "active_sharpe": round(_annualized_sharpe(active), 6),
        }
    return result


def _annualized_sharpe(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if variance <= 0:
        return 0.0
    return mean / (variance**0.5) * (12**0.5)


def _static_checks(
    *,
    development_months: int,
    holdout_months: int,
    overlap_months: int,
    annual_cost_bps: int,
    candidate: LegStats,
    benchmark: LegStats,
) -> dict[str, bool]:
    return {
        "candidate_preregistered": True,
        "development_months": development_months >= 120,
        "holdout_months": holdout_months >= 120,
        "temporal_overlap": overlap_months == 0,
        "annual_cost_bps": annual_cost_bps >= 50,
        "positive_holdout_cagr": candidate.cagr_pct > 0,
        "absolute_holdout_sharpe": candidate.sharpe >= 1.0,
        "absolute_holdout_drawdown": candidate.max_dd_pct <= 10.0,
        "benchmark_sharpe_superiority": candidate.sharpe > benchmark.sharpe,
        "benchmark_drawdown_ratio": candidate.max_dd_pct <= benchmark.max_dd_pct * 0.8,
    }


def build_operational_canary_evidence(
    *,
    dates: Sequence[str],
    candidate_monthly_factors: Sequence[float],
    benchmark_monthly_factors: Sequence[float],
    development_months: int,
    annual_cost_bps: int,
    code_commit: str,
    generated_at_utc: str,
    strategy_fingerprint: str,
) -> dict[str, Any]:
    """Build no-order evidence from a frozen exact deployment time split."""

    if not (
        len(dates)
        == len(candidate_monthly_factors)
        == len(benchmark_monthly_factors)
    ):
        raise ValueError("dates and monthly factors must align")
    if development_months < 1 or development_months >= len(dates):
        raise ValueError("development_months must leave a non-empty holdout")
    if any(float(value) <= 0 for value in candidate_monthly_factors):
        raise ValueError("candidate monthly factors must be positive")
    if any(float(value) <= 0 for value in benchmark_monthly_factors):
        raise ValueError("benchmark monthly factors must be positive")

    candidate_net = apply_annual_cost_drag(
        candidate_monthly_factors,
        annual_cost_bps=annual_cost_bps,
    )
    holdout_candidate = candidate_net[development_months:]
    holdout_benchmark = [float(value) for value in benchmark_monthly_factors[development_months:]]
    development_stats = summarize(candidate_net[:development_months])
    candidate_stats = summarize(holdout_candidate)
    benchmark_stats = summarize(holdout_benchmark)
    checks = _static_checks(
        development_months=development_months,
        holdout_months=len(holdout_candidate),
        overlap_months=0,
        annual_cost_bps=annual_cost_bps,
        candidate=candidate_stats,
        benchmark=benchmark_stats,
    )
    eligible = all(checks.values())
    months = [str(value) for value in dates]
    fingerprint = _data_fingerprint(
        months=months,
        candidate_factors=candidate_net,
        benchmark_factors=benchmark_monthly_factors,
        development_months=development_months,
        annual_cost_bps=annual_cost_bps,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "route": ROUTE,
        "code_commit": code_commit,
        "generated_at_utc": generated_at_utc,
        "candidate_id": CANDIDATE_ID,
        "strategy_fingerprint": strategy_fingerprint,
        "data_fingerprint": fingerprint,
        "split": {
            "development_start": months[0],
            "development_end": months[development_months - 1],
            "holdout_start": months[development_months],
            "holdout_end": months[-1],
            "development_months": development_months,
            "holdout_months": len(months) - development_months,
            "overlap_months": 0,
        },
        "cost_model": {
            "base_annual_bps": annual_cost_bps,
            "diagnostic_annual_bps": [100, 150],
        },
        "development": _performance(development_stats),
        "holdout": {
            "months": months[development_months:],
            "candidate_monthly_factors": [
                round(value, 12) for value in holdout_candidate
            ],
            "benchmark_monthly_factors": [
                round(value, 12) for value in holdout_benchmark
            ],
            "candidate": _performance(candidate_stats),
            "benchmark": _performance(benchmark_stats),
        },
        "checks": checks,
        "diagnostics": {
            "alpha_confirmed": False,
            "active_psr": _active_psr(holdout_candidate, holdout_benchmark),
            "cost_sensitivity": _cost_sensitivity(
                holdout_candidate,
                holdout_benchmark,
                base_annual_bps=annual_cost_bps,
            ),
        },
        "decision": {
            "verdict": READY if eligible else BLOCKED,
            "eligible": eligible,
            "alpha_confirmed": False,
            "capital_fraction": 0.1 if eligible else 0,
            "max_rung": 1 if eligible else 0,
            "promotion_above_rung1_allowed": False,
        },
        "safety": {
            "orders_submitted": 0,
            "capital_changed": False,
            "live_strategy_changed": False,
        },
        "_fingerprint_source": {
            "all_months": months,
            "candidate_monthly_factors": [round(value, 12) for value in candidate_net],
            "benchmark_monthly_factors": [
                round(float(value), 12) for value in benchmark_monthly_factors
            ],
        },
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _close(left: Any, right: Any, *, tolerance: float = 1e-6) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def assess_operational_canary_evidence(
    evidence: Any,
    *,
    expected_code_commit: str | None = None,
    expected_strategy_fingerprint: str | None = None,
    live_strategy_fingerprint: str | None = None,
    evidence_age_hours: float | None = None,
    max_evidence_age_hours: float = MAX_EVIDENCE_AGE_HOURS,
) -> OperationalCanaryAssessment:
    """Independently reconstruct the typed contract and fail closed on drift."""

    payload = _mapping(evidence)
    split = _mapping(payload.get("split"))
    cost = _mapping(payload.get("cost_model"))
    holdout = _mapping(payload.get("holdout"))
    source = _mapping(payload.get("_fingerprint_source"))
    decision = _mapping(payload.get("decision"))
    safety = _mapping(payload.get("safety"))
    candidate_factors = [
        float(value) for value in _sequence(holdout.get("candidate_monthly_factors"))
    ]
    benchmark_factors = [
        float(value) for value in _sequence(holdout.get("benchmark_monthly_factors"))
    ]
    candidate_snapshot = _mapping(holdout.get("candidate"))
    benchmark_snapshot = _mapping(holdout.get("benchmark"))
    development_snapshot = _mapping(payload.get("development"))

    aligned = bool(candidate_factors) and len(candidate_factors) == len(benchmark_factors)
    positive = aligned and all(value > 0 for value in candidate_factors + benchmark_factors)
    if positive:
        candidate_stats = summarize(candidate_factors)
        benchmark_stats = summarize(benchmark_factors)
        active_psr = _active_psr(candidate_factors, benchmark_factors)
    else:
        candidate_stats = summarize([1.0, 1.0])
        benchmark_stats = summarize([1.0, 1.0])
        active_psr = None

    development_months = split.get("development_months")
    holdout_months = split.get("holdout_months")
    overlap_months = split.get("overlap_months")
    annual_cost_bps = cost.get("base_annual_bps")
    try:
        dev_n = int(development_months)
        hold_n = int(holdout_months)
        overlap_n = int(overlap_months)
        cost_bps = int(annual_cost_bps)
    except (TypeError, ValueError):
        dev_n = hold_n = overlap_n = cost_bps = -1

    source_months = [str(value) for value in _sequence(source.get("all_months"))]
    source_candidate = [
        float(value) for value in _sequence(source.get("candidate_monthly_factors"))
    ]
    source_benchmark = [
        float(value) for value in _sequence(source.get("benchmark_monthly_factors"))
    ]
    fingerprint_recomputed = None
    if (
        dev_n > 0
        and len(source_months) == len(source_candidate) == len(source_benchmark)
        and len(source_months) == dev_n + hold_n
        and len(candidate_factors) == len(benchmark_factors) == hold_n
    ):
        fingerprint_recomputed = _data_fingerprint(
            months=source_months,
            candidate_factors=[*source_candidate[:dev_n], *candidate_factors],
            benchmark_factors=[*source_benchmark[:dev_n], *benchmark_factors],
            development_months=dev_n,
            annual_cost_bps=cost_bps,
        )

    raw_checks = _static_checks(
        development_months=dev_n,
        holdout_months=hold_n,
        overlap_months=overlap_n,
        annual_cost_bps=cost_bps,
        candidate=candidate_stats,
        benchmark=benchmark_stats,
    )
    candidate_matches = all(
        (
            candidate_snapshot.get("n_months") == candidate_stats.n_months,
            _close(candidate_snapshot.get("cagr_pct"), candidate_stats.cagr_pct),
            _close(candidate_snapshot.get("sharpe"), candidate_stats.sharpe),
            _close(candidate_snapshot.get("max_drawdown_pct"), candidate_stats.max_dd_pct),
        )
    )
    benchmark_matches = all(
        (
            benchmark_snapshot.get("n_months") == benchmark_stats.n_months,
            _close(benchmark_snapshot.get("cagr_pct"), benchmark_stats.cagr_pct),
            _close(benchmark_snapshot.get("sharpe"), benchmark_stats.sharpe),
            _close(benchmark_snapshot.get("max_drawdown_pct"), benchmark_stats.max_dd_pct),
        )
    )
    checks = {
        "schema_version": payload.get("schema_version") == SCHEMA_VERSION,
        "role": payload.get("role") == ROLE,
        "route": payload.get("route") == ROUTE,
        "candidate_id": payload.get("candidate_id") == CANDIDATE_ID,
        "code_commit_format": isinstance(payload.get("code_commit"), str)
        and bool(_SHA_RE.fullmatch(str(payload.get("code_commit")))),
        "code_commit": expected_code_commit is not None
        and payload.get("code_commit") == expected_code_commit,
        "strategy_fingerprint_format": isinstance(payload.get("strategy_fingerprint"), str)
        and bool(_FINGERPRINT_RE.fullmatch(str(payload.get("strategy_fingerprint")))),
        "strategy_fingerprint": expected_strategy_fingerprint is not None
        and payload.get("strategy_fingerprint") == expected_strategy_fingerprint,
        "live_strategy_fingerprint": expected_strategy_fingerprint is not None
        and live_strategy_fingerprint == expected_strategy_fingerprint,
        "evidence_fresh": evidence_age_hours is not None
        and 0 <= evidence_age_hours <= max_evidence_age_hours,
        "raw_factors_aligned": aligned,
        "raw_factors_positive": positive,
        "data_fingerprint": fingerprint_recomputed is not None
        and payload.get("data_fingerprint") == fingerprint_recomputed,
        "candidate_snapshot_matches_raw": candidate_matches,
        "benchmark_snapshot_matches_raw": benchmark_matches,
        "development_snapshot_present": development_snapshot.get("n_months") == dev_n,
        **{f"historical_{key}": value for key, value in raw_checks.items()},
        "decision_bounded": decision.get("eligible") is True
        and decision.get("verdict") == READY
        and decision.get("alpha_confirmed") is False
        and decision.get("capital_fraction") == 0.1
        and decision.get("max_rung") == 1
        and decision.get("promotion_above_rung1_allowed") is False,
        "safety_no_side_effect": safety.get("orders_submitted") == 0
        and safety.get("capital_changed") is False
        and safety.get("live_strategy_changed") is False,
    }
    eligible = all(checks.values())
    reasons = tuple(key for key, passed in checks.items() if not passed)
    return OperationalCanaryAssessment(
        eligible=eligible,
        alpha_confirmed=False,
        capital_fraction=0.1 if eligible else 0.0,
        max_rung=1 if eligible else 0,
        candidate_id=(str(payload.get("candidate_id")) if payload.get("candidate_id") else None),
        strategy_fingerprint=(
            str(payload.get("strategy_fingerprint"))
            if payload.get("strategy_fingerprint")
            else None
        ),
        reasons=reasons,
        checks=checks,
        recomputed={
            "candidate": _performance(candidate_stats),
            "benchmark": _performance(benchmark_stats),
            "active_psr": active_psr,
            "cost_sensitivity": (
                _cost_sensitivity(
                    candidate_factors,
                    benchmark_factors,
                    base_annual_bps=cost_bps,
                )
                if positive
                else {}
            ),
        },
    )


__all__ = [
    "BLOCKED",
    "CANDIDATE_ID",
    "MAX_EVIDENCE_AGE_HOURS",
    "OperationalCanaryAssessment",
    "READY",
    "ROLE",
    "ROUTE",
    "assess_operational_canary_evidence",
    "build_operational_canary_evidence",
]
