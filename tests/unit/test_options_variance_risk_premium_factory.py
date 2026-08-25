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
    parse_fama_french_daily,
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
            }
            for index in range(736)
        ],
    }


def _calibration() -> dict:
    return {
        "gate_version": "2.0",
        "verdict": "CALIBRATED",
        "code_commit": "abc123",
        "scenario": {"repetitions": 500},
        "thresholds": {"holdout_psr_min": 0.95, "paper_psr_min": 0.80},
        "family_calibrations": {
            "16": {
                "live_calibrated": True,
                "null_false_acceptance_rate": 0.04,
                "target_live_detection_rate": 0.84,
            }
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
    assert payload["prior_trial_count"] == 736
    assert payload["global_audit_trial_count"] == 752
    assert payload["unique_trial_fingerprint_count"] == 752
    assert payload["split"]["development_months"] == 84
    assert payload["split"]["embargo_months"] == 1
    assert payload["split"]["holdout_months"] >= 120
    assert payload["model_chronology"]["passed"] is True
    assert payload["decision"]["research_canary_eligible"] is False
    assert payload["research_live_parity"]["passed"] is False
    assert all(
        row["retroactive_promotion_allowed"] is False for row in payload["prior_adoption_audit"]
    )
