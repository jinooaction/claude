from __future__ import annotations

import io
import math
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from auto_invest.analytics.options_variance_risk_premium_factory import (
    OptionsPremiumBundle,
    OptionsPremiumPolicy,
    VarianceRiskPremiumSnapshot,
    _classify_verdict,
    _development_winner_index,
    audit_prior_adoption,
    expected_shortfall_95,
    generate_options_premium_candidates,
    options_target_weight,
    parse_cboe_put_history,
    parse_cboe_vix_history,
    parse_cboe_wput_history,
    parse_fama_french_daily,
    portfolio_adoption_lane,
    premium_existence_lane,
    run_options_variance_risk_premium_factory,
    standalone_premium_lane,
    validate_options_premium_bundle,
)


def _months(count: int, *, year: int = 2007, month: int = 3) -> list[str]:
    output: list[str] = []
    for _ in range(count):
        output.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def _bundle(count: int = 220) -> OptionsPremiumBundle:
    months = _months(count)
    put = tuple(1.009 + 0.018 * math.sin(index * 1.7) for index in range(count))
    wput = tuple(1.0085 + 0.019 * math.sin(index * 1.83) for index in range(count))
    market = tuple(1.006 + 0.045 * math.sin(index * 1.3) for index in range(count))
    cash = tuple(1.002 for _ in range(count))
    features: dict[int, tuple[VarianceRiskPremiumSnapshot, ...]] = {}
    for horizon in (6, 12):
        rows = []
        for index, month in enumerate(months):
            rows.append(
                VarianceRiskPremiumSnapshot(
                    target_month=date.fromisoformat(month),
                    source_month=_previous_month(date.fromisoformat(month)),
                    horizon_months=horizon,
                    vix_level=18.0 + math.sin(index / 5),
                    implied_variance=0.04,
                    realized_variance=0.025,
                    variance_premium=0.015,
                    smoothed_variance_premium=0.012,
                    equity_trend=0.08,
                    market_drawdown=-0.03,
                    vix_shock=index % 17 == 0,
                    put_excess_lag=0.006,
                )
            )
        features[horizon] = tuple(rows)
    return OptionsPremiumBundle(
        factor_months=tuple(months),
        put_factors=put,
        wput_factors=wput,
        market_factors=market,
        cash_factors=cash,
        features=features,
        quality={"complete": True, "factor_months": count},
    )


def _prior() -> dict:
    return {
        "energy_cross_market_data_fingerprint": "sha256:prior-energy",
        "audit_records": [
            {
                "candidate_id": f"prior-{index:03d}",
                "strategy_fingerprint": f"sha256:prior-{index:03d}",
                "status": "complete",
                "batch_id": "strategy-factory-test-prior",
            }
            for index in range(736)
        ],
    }


def _calibration() -> dict:
    return {
        "gate_version": "2.0",
        "research_entry_gate_version": "3.1",
        "verdict": "CALIBRATED",
        "code_commit": "abc123",
        "scenario": {"seed": 60_000, "repetitions": 500},
        "thresholds": {
            "holdout_psr_min": 0.95,
            "paper_psr_min": 0.80,
            "research_entry_pbo_max": 0.25,
        },
        "required": {
            "family_false_acceptance_max": 0.01,
            "detection_min": 0.80,
            "program_false_acceptance_budget": 0.20,
            "maximum_research_families": 20,
        },
        "family_calibrations": {
            "16": {
                "live_calibrated": True,
                "null_false_acceptance_rate": 0.04,
                "target_live_detection_rate": 0.84,
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


def _controls() -> dict:
    return {
        "verdict": "FULL_GATE_CONTROLS_VALID",
        "promotion_control_passed": True,
        "code_commit": "abc123",
        "control_fingerprint": "sha256:full-controls",
        "positive_control": {"passed": True},
        "null_control": {"passed": False},
    }


def test_cboe_parsers_ignore_sparse_put_rows_and_fail_on_duplicates() -> None:
    put = b"DATE,PUT\n03/04/1991,153.5\n01/03/2007,700\n01/04/2007,701\n"
    parsed = parse_cboe_put_history(put)
    assert parsed.ignored_pre_continuous_rows == 1
    assert parsed.rows[0] == (date(2007, 1, 3), 700.0)

    vix = b"DATE,OPEN,HIGH,LOW,CLOSE\n01/03/2007,12,13,11,12.5\n01/04/2007,13,14,12,13.5\n"
    assert parse_cboe_vix_history(vix).rows[0][1] == pytest.approx(12.5)
    with pytest.raises(ValueError, match="duplicated"):
        parse_cboe_put_history(put + b"01/04/2007,702\n")


def test_wput_parser_enforces_the_independent_source_contract() -> None:
    raw = b"DATE,WPUT\n01/31/2006,100\n02/01/2006,100.5\n"
    parsed = parse_cboe_wput_history(raw)
    assert parsed.rows[0] == (date(2006, 1, 31), 100.0)
    with pytest.raises(ValueError, match="header mismatch"):
        parse_cboe_wput_history(raw.replace(b"DATE,WPUT", b"DATE,PUT"))
    with pytest.raises(ValueError, match="duplicated"):
        parse_cboe_wput_history(raw + b"02/01/2006,101\n")


def test_fama_french_daily_parser_keeps_market_and_cash_returns() -> None:
    lines = ["note", ",Mkt-RF,SMB,HML,RF", "20070103,1.00,0,0,0.01", "20070104,-0.50,0,0,0.01"]
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("F-F_Research_Data_Factors_daily.csv", "\n".join(lines))
    rows = parse_fama_french_daily(raw.getvalue())
    assert rows[0].market_return == pytest.approx(0.0101)
    assert rows[0].cash_return == pytest.approx(0.0001)


def test_candidate_grammar_has_four_passive_and_twelve_dynamic_policies() -> None:
    candidates = generate_options_premium_candidates()
    assert len(candidates) == 16
    assert len({row.candidate_id for row in candidates}) == 16
    assert len({row.strategy_fingerprint for row in candidates}) == 16
    assert sum(row.policy.family == "passive_put" for row in candidates) == 4
    assert {row.policy.family for row in candidates} == {
        "passive_put",
        "positive_vrp",
        "tail_guarded",
        "ridge_forecast",
    }


def test_policy_weights_and_ridge_inputs_are_preregistered() -> None:
    feature = _bundle().features[6][5]
    assert options_target_weight(
        OptionsPremiumPolicy("passive_put", None, Decimal("0.25")), feature
    ) == Decimal("0.25")
    assert options_target_weight(
        OptionsPremiumPolicy("positive_vrp", 6, Decimal("0.5")), feature
    ) == Decimal("0.5")
    assert options_target_weight(
        OptionsPremiumPolicy("ridge_forecast", 6, Decimal("1")),
        feature,
        ridge_prediction=-0.001,
    ) == Decimal("0")


def test_expected_shortfall_and_standalone_lane_include_tail_gates() -> None:
    cash = [1.001] * 140
    market = [1.006 + 0.05 * math.sin(index * 1.9) for index in range(140)]
    candidate = [1.009 + 0.018 * math.sin(index * 1.7) for index in range(140)]
    lane = standalone_premium_lane(candidate, cash, market, paper=False)
    assert expected_shortfall_95(candidate) < 0
    assert {"maximum_drawdown", "expected_shortfall_95"} <= set(lane["gates"])
    assert "active_fraction" not in lane["gates"]


def test_premium_existence_is_not_confused_with_portfolio_adoption() -> None:
    count = 180
    cash = [1.002] * count
    candidate = [1.008 + 0.004 * math.sin(index * 1.7) for index in range(count)]
    stronger_market = [1.012 + 0.006 * math.sin(index * 1.3) for index in range(count)]
    premium = premium_existence_lane(candidate, cash)
    adoption = portfolio_adoption_lane(candidate, cash, stronger_market)
    assert premium["passed"] is True
    assert adoption["passed"] is False
    assert premium["promotion_eligible"] is False
    assert adoption["promotion_eligible"] is False


def test_development_tie_breaks_on_tail_loss_then_drawdown_and_identity() -> None:
    records = [
        {
            "candidate_id": "b",
            "development_sharpe": 0.5,
            "development_expected_shortfall_loss_pct": 4.0,
            "development_max_drawdown_pct": 8.0,
        },
        {
            "candidate_id": "a",
            "development_sharpe": 0.5,
            "development_expected_shortfall_loss_pct": 3.0,
            "development_max_drawdown_pct": 9.0,
        },
        {
            "candidate_id": "c",
            "development_sharpe": 0.5,
            "development_expected_shortfall_loss_pct": 3.0,
            "development_max_drawdown_pct": 10.0,
        },
    ]
    assert _development_winner_index(records) == 1


def test_reference_failure_overrides_a_selected_paper_candidate() -> None:
    assert (
        _classify_verdict(
            infrastructure_passed=True,
            selected_live_passed=False,
            selected_paper_passed=True,
            reference_adoption_passed=False,
            objective_calibration_passed=True,
        )
        == "GATE_OR_REFERENCE_SUSPECT"
    )


def test_prior_adoption_audit_never_retroactively_promotes() -> None:
    audit = audit_prior_adoption(
        {
            "energy": {
                "decision": {
                    "verdict": "NO_FACTORY_EDGE",
                    "criterion_diagnosis": "OBJECTIVE_GATE_PASSABLE_CANDIDATE_UNCONFIRMED",
                }
            },
            "credit": {"decision": {"verdict": "PAPER_CHALLENGER", "paper_candidate_id": "x"}},
        }
    )
    assert len(audit) == 2
    assert all(row["retroactive_promotion_allowed"] is False for row in audit)


def test_incomplete_bundle_fails_before_publication() -> None:
    bundle = _bundle()
    object.__setattr__(bundle, "quality", {"complete": False})
    with pytest.raises(ValueError, match="incomplete or stale"):
        validate_options_premium_bundle(bundle)


def test_factory_preserves_736_trials_and_appends_exactly_16() -> None:
    payload = run_options_variance_risk_premium_factory(
        _bundle(),
        prior_factory_payload=_prior(),
        prior_family_payloads={"energy": {"decision": {"verdict": "NO_FACTORY_EDGE"}}},
        calibration_evidence=_calibration(),
        full_gate_controls=_controls(),
        code_commit="abc123",
        timestamp_utc="2026-08-26T00:00:00Z",
        calibration_repetitions=100,
    )
    assert payload["candidate_count"] == 16
    assert payload["gate_version"] == "3.1"
    assert payload["prior_trial_count"] == 736
    assert payload["global_audit_trial_count"] == 752
    assert payload["program_research_family_count"] == 2
    assert len(payload["research_family_audit"]) == 2
    assert all("research_family_id" in row for row in payload["audit_records"])
    assert payload["unique_trial_fingerprint_count"] == 752
    gate_by_id = {row["gate_id"]: row for row in payload["decision"]["gates"]}
    assert gate_by_id["complete_family_trials"]["actual"] == "16"
    assert gate_by_id["prior_audit_complete"]["actual"] == "736"
    assert gate_by_id["global_audit_trials"]["actual"] == "752"
    assert gate_by_id["unique_audit_fingerprints"]["actual"] == "752"
    assert payload["split"]["development_months"] == 84
    assert payload["split"]["embargo_months"] == 1
    assert payload["split"]["holdout_months"] >= 120
    assert payload["model_chronology"]["passed"] is True
    assert payload["decision"]["research_canary_eligible"] is False
    assert payload["decision"]["paper_forward_eligible"] is False
    assert payload["promotion_allowed"] is False
    assert payload["research_live_parity"]["passed"] is False
    assert payload["selection_repair"]["protocol"] == {
        "outer_train_months": 84,
        "outer_embargo_months": 1,
        "outer_test_months": 12,
        "inner_train_months": 48,
        "inner_embargo_months": 1,
        "inner_validation_months": 12,
        "independent_index": "WPUT",
        "independent_index_used_for_selection": False,
    }
    assert payload["legacy_selection"]["decision"]["pbo"] is not None
    assert all(len(row["segment_sharpes"]) == 8 for row in payload["trial_records"])
    assert len(payload["development_segment_sharpes"]) == 16
    assert all(len(row) == 8 for row in payload["development_segment_sharpes"])
    chronology = payload["selection_repair"]["chronology"]
    assert chronology["all_folds_valid"] is True
    assert chronology["fold_count"] >= 8
    assert all(
        len(row["inner_folds"]) >= 2
        for row in payload["selection_repair"]["portfolio_selection"]["outer_folds"]
    )
    assert set(payload["objective_lanes"]) == {
        "premium_existence",
        "portfolio_adoption",
        "timing_value",
    }
    assert all(
        row["diagnostic_only"] is True and row["promotion_eligible"] is False
        for row in payload["objective_lanes"].values()
    )
    assert payload["legacy_selection"]["decision"]["verdict"] in {
        "FACTORY_EDGE_CONFIRMED",
        "PAPER_EDGE_CANDIDATE",
        "REFERENCE_EDGE_CONFIRMED_SELECTION_UNCONFIRMED",
        "GATE_OR_REFERENCE_SUSPECT",
        "NO_FACTORY_EDGE",
    }
    assert all(
        row["retroactive_promotion_allowed"] is False for row in payload["prior_adoption_audit"]
    )


def test_wput_changes_cannot_change_put_selected_candidates_or_weights() -> None:
    original = _bundle()
    mutated = _bundle()
    object.__setattr__(
        mutated,
        "wput_factors",
        tuple(1.015 + 0.06 * math.sin(index * 2.31) for index in range(220)),
    )

    def run(bundle: OptionsPremiumBundle) -> dict:
        return run_options_variance_risk_premium_factory(
            bundle,
            prior_factory_payload=_prior(),
            prior_family_payloads={},
            calibration_evidence=_calibration(),
            full_gate_controls=_controls(),
            code_commit="abc123",
            timestamp_utc="2026-08-26T00:00:00Z",
            calibration_repetitions=10,
        )

    first = run(original)["selection_repair"]
    second = run(mutated)["selection_repair"]
    for lane in ("portfolio_selection", "timing_selection"):
        first_selection = [
            (row["selected_candidate_id"], row["selected_weights"])
            for row in first[lane]["outer_folds"]
        ]
        second_selection = [
            (row["selected_candidate_id"], row["selected_weights"])
            for row in second[lane]["outer_folds"]
        ]
        assert first_selection == second_selection
