from __future__ import annotations

import io
import math
import zipfile
from copy import deepcopy
from datetime import date

import pytest

from auto_invest.analytics.accounting_factor_factory import (
    EXPECTED_CANDIDATES,
    EXPECTED_GLOBAL_AUDIT_TRIALS,
    EXPECTED_PROGRAM_FAMILIES,
    AccountingFactorMonth,
    build_accounting_factor_bundle,
    generate_accounting_factor_candidates,
    parse_fama_french_five_factor_zip,
    run_accounting_factor_factory,
)


def _month_rows(end_year: int = 2026, end_month: int = 6) -> list[AccountingFactorMonth]:
    rows: list[AccountingFactorMonth] = []
    year, month = 1963, 7
    index = 0
    while (year, month) <= (end_year, end_month):
        cycle = math.sin(index / 9.0) * 0.004
        rows.append(
            AccountingFactorMonth(
                observed_month=date(year, month, 1),
                market_excess=0.006 + cycle,
                size=0.001,
                value=0.005 + cycle,
                profitability=0.004 - cycle / 3,
                investment=0.003 + cycle / 4,
                cash=0.002,
            )
        )
        index += 1
        month += 1
        if month == 13:
            year += 1
            month = 1
    return rows


def _bundle():
    current = _month_rows()
    archive = [row for row in current if row.observed_month <= date(2015, 6, 1)]
    return build_accounting_factor_bundle(
        archive,
        current,
        archive_digest="sha256:archive",
        current_digest="sha256:current",
        current_date=date(2026, 8, 31),
    )


def _prior_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for family in range(19):
        count = 46 if family == 18 else 41
        for index in range(count):
            rows.append(
                {
                    "candidate_id": f"legacy-{family:02d}-{index:03d}",
                    "strategy_fingerprint": f"sha256:legacy-{family:02d}-{index:03d}",
                    "status": "complete",
                    "batch_id": f"legacy-family-{family:02d}",
                    "research_family_id": f"legacy-factory:legacy-family-{family:02d}",
                }
            )
    assert len(rows) == 784
    return rows


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


def _run(bundle=None) -> dict[str, object]:
    return run_accounting_factor_factory(
        bundle=bundle or _bundle(),
        prior_audit_records=_prior_rows(),
        calibration=_calibration(),
        code_commit="abc123",
        generated_at="2026-08-31T00:00:00Z",
    )


def _zip_payload(rows: list[str], header: str = ",Mkt-RF,SMB,HML,RMW,CMA,RF") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "F-F_Research_Data_5_Factors_2x3.csv",
            "metadata\n" + header + "\n" + "\n".join(rows) + "\n\n Annual Factors\n",
        )
    return output.getvalue()


def test_generates_exactly_sixteen_preregistered_no_live_candidates() -> None:
    candidates = generate_accounting_factor_candidates()

    assert len(candidates) == EXPECTED_CANDIDATES == 16
    assert len({row.candidate_id for row in candidates}) == 16
    assert len({row.strategy_fingerprint for row in candidates}) == 16
    assert {row.policy.sleeve_scale for row in candidates} == {0.5, 1.0}
    assert {row.policy.profile for row in candidates} == {
        "hml",
        "rmw",
        "cma",
        "hml-rmw",
        "hml-cma",
        "rmw-cma",
        "equal-three",
        "defensive-three",
    }
    assert all(row.as_dict()["live_expressible"] is False for row in candidates)


def test_zip_parser_reads_monthly_table_and_rejects_bad_shapes() -> None:
    parsed = parse_fama_french_five_factor_zip(
        _zip_payload(["196307,1.00,2.00,3.00,4.00,5.00,0.25"])
    )
    assert parsed == (
        AccountingFactorMonth(date(1963, 7, 1), 0.01, 0.02, 0.03, 0.04, 0.05, 0.0025),
    )

    with pytest.raises(ValueError, match="duplicated"):
        parse_fama_french_five_factor_zip(
            _zip_payload(
                [
                    "196307,1.00,2.00,3.00,4.00,5.00,0.25",
                    "196307,1.00,2.00,3.00,4.00,5.00,0.25",
                ]
            )
        )
    with pytest.raises(ValueError, match="increase"):
        parse_fama_french_five_factor_zip(
            _zip_payload(
                [
                    "196308,1.00,2.00,3.00,4.00,5.00,0.25",
                    "196307,1.00,2.00,3.00,4.00,5.00,0.25",
                ]
            )
        )
    with pytest.raises(ValueError, match="columns"):
        parse_fama_french_five_factor_zip(
            _zip_payload(["196307,1,2,3,4,0.25"], header=",Mkt-RF,SMB,HML,RMW,RF")
        )
    with pytest.raises(ValueError, match="missing sentinel"):
        parse_fama_french_five_factor_zip(
            _zip_payload(["196307,1.00,2.00,-99.99,4.00,5.00,0.25"])
        )
    with pytest.raises(ValueError, match="finite"):
        parse_fama_french_five_factor_zip(
            _zip_payload(["196307,1.00,2.00,nan,4.00,5.00,0.25"])
        )


def test_bundle_separates_vintage_development_embargo_and_current_holdout() -> None:
    bundle = _bundle()

    assert bundle.development[0].observed_month == date(1963, 7, 1)
    assert bundle.development[-1].observed_month == date(2013, 12, 1)
    assert len(bundle.development) == 606
    assert len(bundle.embargo) == 12
    assert bundle.holdout[0].observed_month == date(2015, 1, 1)
    assert bundle.holdout[-1].observed_month == date(2026, 6, 1)
    assert bundle.quality["archive_content_digest"] == "sha256:archive"
    assert bundle.quality["current_content_digest"] == "sha256:current"
    assert bundle.quality["development_revision_count"] == 0


def test_bundle_audits_revisions_and_fails_on_month_set_or_current_month() -> None:
    current = _month_rows()
    archive = [row for row in current if row.observed_month <= date(2015, 6, 1)]
    revised = list(current)
    revised[0] = AccountingFactorMonth(
        observed_month=revised[0].observed_month,
        market_excess=revised[0].market_excess,
        size=revised[0].size,
        value=revised[0].value + 0.0001,
        profitability=revised[0].profitability,
        investment=revised[0].investment,
        cash=revised[0].cash,
    )
    bundle = build_accounting_factor_bundle(
        archive,
        revised,
        archive_digest="sha256:a",
        current_digest="sha256:b",
        current_date=date(2026, 8, 31),
    )
    assert bundle.quality["development_revision_count"] == 1
    assert bundle.quality["development_max_abs_revision"] == pytest.approx(0.0001)

    with pytest.raises(ValueError, match="development month set"):
        build_accounting_factor_bundle(
            archive[1:],
            current,
            archive_digest="sha256:a",
            current_digest="sha256:b",
            current_date=date(2026, 8, 31),
        )

    incomplete = [
        *current,
        AccountingFactorMonth(date(2026, 8, 1), 0.01, 0.0, 0.01, 0.01, 0.01, 0.0),
    ]
    dropped = build_accounting_factor_bundle(
        archive,
        incomplete,
        archive_digest="sha256:a",
        current_digest="sha256:b",
        current_date=date(2026, 8, 31),
    )
    assert dropped.quality["dropped_incomplete_month"] == "2026-08"


def test_holdout_mutation_cannot_reselect_development_winner() -> None:
    baseline = _bundle()
    mutated_holdout = tuple(
        AccountingFactorMonth(
            row.observed_month,
            row.market_excess,
            row.size,
            -row.value * 8,
            row.profitability * 9,
            -row.investment * 7,
            row.cash,
        )
        for row in baseline.holdout
    )
    mutated = type(baseline)(
        development=baseline.development,
        embargo=baseline.embargo,
        holdout=mutated_holdout,
        quality=baseline.quality,
    )

    original = _run(baseline)
    changed = _run(mutated)

    assert original["development_selection"] == changed["development_selection"]
    assert original["holdout"] != changed["holdout"]


def test_result_reconstructs_800_rows_20_families_and_all_safety_blocks() -> None:
    result = _run()

    assert result["candidate_count"] == 16
    assert result["global_audit_trial_count"] == EXPECTED_GLOBAL_AUDIT_TRIALS == 800
    assert result["unique_trial_fingerprint_count"] == 800
    assert result["program_research_family_count"] == EXPECTED_PROGRAM_FAMILIES == 20
    assert len(result["research_family_audit"]) == 20
    assert result["program_multiplicity"]["program_false_acceptance_bound"] == "0.20"
    assert result["decision"]["verdict"] in {
        "FACTORY_EDGE",
        "PAPER_CHALLENGER",
        "NO_FACTORY_EDGE",
    }
    assert result["decision"]["selected_deploy_config"] is None
    assert result["decision"]["research_canary_eligible"] is False
    assert result["promotion_allowed"] is False
    assert result["research_live_parity"]["passed"] is False
    assert result["safety"] == {
        "orders_submitted": 0,
        "capital_changed": False,
        "live_strategy_changed": False,
    }


def test_global_audit_and_calibration_fail_closed() -> None:
    with pytest.raises(ValueError, match="784"):
        run_accounting_factor_factory(
            bundle=_bundle(),
            prior_audit_records=_prior_rows()[:-1],
            calibration=_calibration(),
            code_commit="abc123",
            generated_at="2026-08-31T00:00:00Z",
        )
    duplicate = deepcopy(_prior_rows())
    duplicate[-1] = deepcopy(duplicate[0])
    with pytest.raises(ValueError, match="unique"):
        run_accounting_factor_factory(
            bundle=_bundle(),
            prior_audit_records=duplicate,
            calibration=_calibration(),
            code_commit="abc123",
            generated_at="2026-08-31T00:00:00Z",
        )
    bad = _calibration()
    bad["required"]["maximum_research_families"] = 21
    result = run_accounting_factor_factory(
        bundle=_bundle(),
        prior_audit_records=_prior_rows(),
        calibration=bad,
        code_commit="abc123",
        generated_at="2026-08-31T00:00:00Z",
    )
    gate = next(
        row
        for row in result["decision"]["gates"]
        if row["gate_id"] == "repository_calibration"
    )
    assert gate["passed"] is False
    assert result["decision"]["verdict"] == "NO_FACTORY_EDGE"


def test_primary_cost_stress_placebo_and_all_holdout_gates_are_exposed() -> None:
    result = _run()
    holdout = result["holdout"]
    gate_ids = {row["gate_id"] for row in result["decision"]["gates"]}

    assert holdout["primary_150bps_annual_cash_excess"] is not None
    assert holdout["stress_300bps_annual_cash_excess"] is not None
    assert holdout["stress_500bps_annual_cash_excess"] is not None
    assert holdout["sign_flipped_placebo_psr"] is not None
    assert {
        "family_pbo",
        "holdout_excess_psr",
        "holdout_annual_excess",
        "positive_eras",
        "recent_36m_wins",
        "single_year_concentration",
        "top_five_month_concentration",
        "max_drawdown",
        "stress_300bps_positive",
        "sign_flipped_placebo_fails_core",
    } <= gate_ids
