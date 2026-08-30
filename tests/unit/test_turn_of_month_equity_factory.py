from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from auto_invest.analytics.options_variance_risk_premium_factory import (
    FrenchDailyFactor,
)
from auto_invest.analytics.turn_of_month_equity_factory import (
    EXPECTED_GLOBAL_AUDIT_TRIALS,
    EXPECTED_PROGRAM_FAMILIES,
    build_french_daily_bundle,
    generate_calendar_candidates,
    run_turn_of_month_equity_factory,
)


def _synthetic_rows() -> list[FrenchDailyFactor]:
    rows: list[FrenchDailyFactor] = []
    year, month = 1926, 7
    for _ in range(1201):
        for session in range(1, 21):
            boundary = session <= 3 or session == 20
            rows.append(
                FrenchDailyFactor(
                    observed_date=date(year, month, session),
                    market_return=0.0012 if boundary else -0.00005,
                    cash_return=0.00005,
                )
            )
        month += 1
        if month == 13:
            year += 1
            month = 1
    return rows


def _prior_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for family in range(17):
        count = 48 if family == 16 else 44
        for index in range(count):
            rows.append(
                {
                    "candidate_id": f"legacy-{family:02d}-{index:03d}",
                    "strategy_fingerprint": f"sha256:legacy-{family:02d}-{index:03d}",
                    "status": "complete",
                    "batch_id": f"legacy-family-{family:02d}",
                }
            )
    assert len(rows) == 752
    return rows


def _regime_payload() -> dict[str, object]:
    return {
        "family_id": "regime-adaptive-stock-bond-joint-weakness",
        "candidate_count": 16,
        "program_research_family_count": 18,
        "candidate_registry": [
            {
                "candidate_id": f"regime-joint-weakness-{index:03d}",
                "strategy_fingerprint": f"sha256:regime-{index:03d}",
            }
            for index in range(16)
        ],
    }


def _calibration() -> dict[str, object]:
    return {
        "research_entry_gate_version": "3.1",
        "verdict": "CALIBRATED",
        "code_commit": "abc123",
        "scenario": {"seed": 60_000, "repetitions": 500},
        "thresholds": {"holdout_psr_min": 0.95, "research_entry_pbo_max": 0.25},
        "required": {
            "family_false_acceptance_max": 0.01,
            "detection_min": 0.80,
            "program_false_acceptance_budget": 0.20,
            "maximum_research_families": 20,
        },
        "family_calibrations": {
            "16": {
                "research_entry_calibrated": True,
                "null_research_entry_acceptance_rate": 0.01,
                "target_research_entry_detection_rate": 0.84,
            },
            "64": {
                "research_entry_calibrated": True,
                "null_research_entry_acceptance_rate": 0.004,
                "target_research_entry_detection_rate": 0.804,
            },
        },
    }


def _run(rows: list[FrenchDailyFactor] | None = None) -> dict[str, object]:
    bundle = build_french_daily_bundle(
        rows or _synthetic_rows(),
        content_digest="sha256:synthetic",
        current_date=date(2026, 8, 30),
    )
    return run_turn_of_month_equity_factory(
        bundle=bundle,
        prior_audit_records=_prior_rows(),
        released_regime_result=_regime_payload(),
        calibration=_calibration(),
        code_commit="abc123",
        generated_at="2026-08-30T00:00:00Z",
    )


def test_generates_exactly_sixteen_fixed_no_live_candidates() -> None:
    candidates = generate_calendar_candidates()

    assert len(candidates) == 16
    assert len({row.candidate_id for row in candidates}) == 16
    assert len({row.strategy_fingerprint for row in candidates}) == 16
    assert {(row.policy.last_sessions, row.policy.first_sessions) for row in candidates} == {
        (last, first) for last in range(1, 5) for first in range(1, 5)
    }
    assert all(row.as_dict()["live_expressible"] is False for row in candidates)


def test_bundle_rejects_duplicate_and_reversed_dates() -> None:
    rows = _synthetic_rows()
    with pytest.raises(ValueError, match="duplicated"):
        build_french_daily_bundle(
            [rows[0], rows[0], *rows[1:]],
            content_digest="sha256:x",
            current_date=date(2026, 8, 30),
        )
    with pytest.raises(ValueError, match="increase"):
        build_french_daily_bundle(
            list(reversed(rows)),
            content_digest="sha256:x",
            current_date=date(2026, 8, 30),
        )


def test_bundle_drops_current_incomplete_month() -> None:
    rows = _synthetic_rows()
    rows.extend(
        FrenchDailyFactor(date(2026, 8, day), 0.01, 0.0) for day in (3, 4, 5)
    )
    bundle = build_french_daily_bundle(
        rows,
        content_digest="sha256:x",
        current_date=date(2026, 8, 30),
    )

    assert bundle.quality["dropped_incomplete_month"] == "2026-08"
    assert bundle.rows[-1].observed_date < date(2026, 8, 1)


def test_holdout_mutation_cannot_reselect_development_winner() -> None:
    baseline = _synthetic_rows()
    mutated = deepcopy(baseline)
    for index, row in enumerate(mutated):
        if row.observed_date >= date(2007, 1, 1):
            mutated[index] = FrenchDailyFactor(
                row.observed_date,
                -row.market_return,
                row.cash_return,
            )

    first = _run(baseline)
    second = _run(mutated)

    assert first["development_selection"] == second["development_selection"]


def test_restores_regime_and_builds_784_row_19_family_ledger() -> None:
    result = _run()

    assert result["global_audit_trial_count"] == EXPECTED_GLOBAL_AUDIT_TRIALS == 784
    assert result["program_research_family_count"] == EXPECTED_PROGRAM_FAMILIES == 19
    assert len(result["audit_records"]) == 784
    assert len(result["research_family_audit"]) == 19
    assert result["audit_records"][-16:] == result["trial_records"]
    assert {
        row["status"] for row in result["audit_records"][-32:-16]
    } == {"EXPLORATORY_REJECTED"}


def test_result_records_all_historical_gates_and_never_enables_live_money() -> None:
    result = _run()
    decision = result["decision"]
    gate_ids = {row["gate_id"] for row in decision["gates"]}

    assert {
        "family_pbo",
        "holdout_excess_psr",
        "holdout_annual_excess",
        "positive_eras",
        "recent_36m_wins",
        "single_year_concentration",
        "top_five_month_concentration",
        "max_drawdown_vs_market",
        "stress_25bps_positive",
        "shifted_placebo_fails_core",
    } <= gate_ids
    assert result["promotion_allowed"] is False
    assert result["research_live_parity"]["passed"] is False
    assert decision["research_canary_eligible"] is False
    assert decision["selected_deploy_config"] is None
    assert result["safety"] == {
        "orders_submitted": 0,
        "capital_changed": False,
        "live_strategy_changed": False,
    }


def test_wrong_prior_or_regime_counts_fail_closed() -> None:
    bundle = build_french_daily_bundle(
        _synthetic_rows(),
        content_digest="sha256:x",
        current_date=date(2026, 8, 30),
    )
    with pytest.raises(ValueError, match="752"):
        run_turn_of_month_equity_factory(
            bundle=bundle,
            prior_audit_records=_prior_rows()[:-1],
            released_regime_result=_regime_payload(),
            calibration=_calibration(),
            code_commit="abc123",
            generated_at="2026-08-30T00:00:00Z",
        )
    bad_regime = _regime_payload()
    bad_regime["candidate_count"] = 15
    with pytest.raises(ValueError, match="regime"):
        run_turn_of_month_equity_factory(
            bundle=bundle,
            prior_audit_records=_prior_rows(),
            released_regime_result=bad_regime,
            calibration=_calibration(),
            code_commit="abc123",
            generated_at="2026-08-30T00:00:00Z",
        )
