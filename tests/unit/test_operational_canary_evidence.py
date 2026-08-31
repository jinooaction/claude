from __future__ import annotations

from copy import deepcopy

from auto_invest.portfolio.operational_canary_evidence import (
    CANDIDATE_ID,
    assess_operational_canary_evidence,
    build_operational_canary_evidence,
)

_COMMIT = "a" * 40
_FINGERPRINT = "sha256:" + "b" * 64


def _dates(n: int = 360) -> list[str]:
    dates: list[str] = []
    year, month = 1991, 1
    for _ in range(n):
        dates.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return dates


def _factors(up: float, down: float, n: int = 360) -> list[float]:
    return [up if index % 2 == 0 else down for index in range(n)]


def _evidence() -> dict:
    return build_operational_canary_evidence(
        dates=_dates(),
        candidate_monthly_factors=_factors(1.012, 0.998),
        benchmark_monthly_factors=_factors(1.010, 0.985),
        development_months=180,
        annual_cost_bps=50,
        code_commit=_COMMIT,
        generated_at_utc="2026-08-31T01:00:00Z",
        strategy_fingerprint=_FINGERPRINT,
    )


def test_operational_evidence_is_typed_bounded_and_not_an_alpha_claim() -> None:
    evidence = _evidence()
    assessment = assess_operational_canary_evidence(
        evidence,
        expected_code_commit=_COMMIT,
        expected_strategy_fingerprint=_FINGERPRINT,
        live_strategy_fingerprint=_FINGERPRINT,
        evidence_age_hours=2,
    )

    assert evidence["role"] == "operational_canary_entry"
    assert evidence["route"] == "historical-operational-canary-v1"
    assert evidence["candidate_id"] == CANDIDATE_ID
    assert evidence["decision"] == {
        "verdict": "OPERATIONAL_CANARY_READY",
        "eligible": True,
        "alpha_confirmed": False,
        "capital_fraction": 0.1,
        "max_rung": 1,
        "promotion_above_rung1_allowed": False,
    }
    assert evidence["safety"] == {
        "orders_submitted": 0,
        "capital_changed": False,
        "live_strategy_changed": False,
    }
    assert assessment.eligible is True
    assert assessment.alpha_confirmed is False
    assert assessment.max_rung == 1
    assert assessment.capital_fraction == 0.1
    assert assessment.recomputed["active_psr"] == evidence["diagnostics"]["active_psr"]
    assert set(evidence["diagnostics"]["cost_sensitivity"]) == {"100", "150"}


def test_consumer_recomputes_raw_monthly_evidence_instead_of_trusting_summary() -> None:
    evidence = _evidence()
    tampered = deepcopy(evidence)
    tampered["holdout"]["candidate_monthly_factors"] = [0.99] * 180

    assessment = assess_operational_canary_evidence(
        tampered,
        expected_code_commit=_COMMIT,
        expected_strategy_fingerprint=_FINGERPRINT,
        live_strategy_fingerprint=_FINGERPRINT,
        evidence_age_hours=2,
    )

    assert assessment.eligible is False
    assert assessment.checks["data_fingerprint"] is False
    assert assessment.checks["candidate_snapshot_matches_raw"] is False


def test_wrong_role_stale_commit_or_fingerprint_fails_closed() -> None:
    evidence = _evidence()
    cases = []
    wrong_role = deepcopy(evidence)
    wrong_role["role"] = "research_diagnostic"
    cases.append(wrong_role)
    cases.extend([evidence, evidence, evidence])

    assessments = [
        assess_operational_canary_evidence(
            cases[0],
            expected_code_commit=_COMMIT,
            expected_strategy_fingerprint=_FINGERPRINT,
            live_strategy_fingerprint=_FINGERPRINT,
            evidence_age_hours=2,
        ),
        assess_operational_canary_evidence(
            cases[1],
            expected_code_commit="c" * 40,
            expected_strategy_fingerprint=_FINGERPRINT,
            live_strategy_fingerprint=_FINGERPRINT,
            evidence_age_hours=2,
        ),
        assess_operational_canary_evidence(
            cases[2],
            expected_code_commit=_COMMIT,
            expected_strategy_fingerprint="sha256:" + "d" * 64,
            live_strategy_fingerprint=_FINGERPRINT,
            evidence_age_hours=2,
        ),
        assess_operational_canary_evidence(
            cases[3],
            expected_code_commit=_COMMIT,
            expected_strategy_fingerprint=_FINGERPRINT,
            live_strategy_fingerprint=_FINGERPRINT,
            evidence_age_hours=40,
        ),
    ]

    assert all(not assessment.eligible for assessment in assessments)
    assert assessments[0].checks["role"] is False
    assert assessments[1].checks["code_commit"] is False
    assert assessments[2].checks["strategy_fingerprint"] is False
    assert assessments[3].checks["evidence_fresh"] is False


def test_live_strategy_must_match_the_validated_candidate_not_only_the_artifact() -> None:
    assessment = assess_operational_canary_evidence(
        _evidence(),
        expected_code_commit=_COMMIT,
        expected_strategy_fingerprint=_FINGERPRINT,
        live_strategy_fingerprint="sha256:" + "e" * 64,
        evidence_age_hours=2,
    )

    assert assessment.eligible is False
    assert assessment.checks["live_strategy_fingerprint"] is False


def test_short_split_or_weak_absolute_performance_is_never_eligible() -> None:
    short = build_operational_canary_evidence(
        dates=_dates(240),
        candidate_monthly_factors=_factors(1.012, 0.998, 240),
        benchmark_monthly_factors=_factors(1.010, 0.985, 240),
        development_months=121,
        annual_cost_bps=50,
        code_commit=_COMMIT,
        generated_at_utc="2026-08-31T01:00:00Z",
        strategy_fingerprint=_FINGERPRINT,
    )
    weak = build_operational_canary_evidence(
        dates=_dates(),
        candidate_monthly_factors=_factors(1.001, 0.980),
        benchmark_monthly_factors=_factors(1.010, 0.985),
        development_months=180,
        annual_cost_bps=50,
        code_commit=_COMMIT,
        generated_at_utc="2026-08-31T01:00:00Z",
        strategy_fingerprint=_FINGERPRINT,
    )

    assert short["decision"]["eligible"] is False
    assert short["checks"]["holdout_months"] is False
    assert weak["decision"]["eligible"] is False
    assert any(not passed for passed in weak["checks"].values())
