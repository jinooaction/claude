"""Preregistered low-turnover regime challenger contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from auto_invest.analytics.global_trend import global_trend_factors
from auto_invest.analytics.regime_adaptive_challenger import (
    CandidateSpec,
    apply_cost_model,
    build_strategy_path,
    evaluate_regime_challenger,
    registered_candidates,
    validate_report_payload,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    ROOT
    / "specs"
    / "171-parallel-regime-edge-challenger"
    / "contracts"
    / "preregistered-challenger.json"
)


def _monthly_fixture(months: int = 624) -> tuple[list[MonthlyRow], list[float]]:
    rows: list[MonthlyRow] = []
    gold: list[float] = []
    stock_price = 100.0
    gold_price = 100.0
    year, month = 1971, 1
    for index in range(months):
        crisis = index % 84 in range(55, 62)
        stock_price *= 0.965 if crisis else (1.011 if index % 5 else 0.996)
        gold_price *= 1.022 if crisis else (1.004 if index % 4 else 0.995)
        long_rate = 3.0 + (index % 48) * 0.08 if crisis else 5.0 - (index % 36) * 0.04
        rows.append(
            MonthlyRow(
                date=f"{year:04d}-{month:02d}-01",
                price=stock_price,
                dividend=2.0,
                long_rate=max(long_rate, 0.5),
            )
        )
        gold.append(gold_price)
        month += 1
        if month == 13:
            year += 1
            month = 1
    return rows, gold


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _forward_contract() -> dict:
    path = (
        ROOT
        / "specs"
        / "172-strategy-acceptance-path-audit"
        / "contracts"
        / "regime-forward-observation.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_registered_grid_is_exactly_the_frozen_sixteen() -> None:
    candidates = registered_candidates()

    assert len(candidates) == 16
    assert len({candidate.candidate_id for candidate in candidates}) == 16
    assert len({candidate.fingerprint for candidate in candidates}) == 16
    assert {candidate.correlation_window_months for candidate in candidates} == {12, 24}
    assert {candidate.correlation_threshold for candidate in candidates} == {0.0, 0.2}
    assert {candidate.joint_weakness_lookback_months for candidate in candidates} == {3, 6}
    assert {candidate.defensive_action for candidate in candidates} == {"cash", "gold"}


def test_weights_are_long_only_fully_funded_and_turnover_is_one_way() -> None:
    rows, gold = _monthly_fixture()
    path = build_strategy_path(rows, gold, registered_candidates()[0])

    assert len(path.weights) == len(rows) - 1
    assert len(path.gross_factors) == len(path.weights) == len(path.one_way_turnover)
    for weights in path.weights:
        assert all(0.0 <= weight <= 1.0 for weight in weights)
        assert sum(weights) == pytest.approx(1.0)
    assert path.one_way_turnover[0] == pytest.approx(
        0.5
        * sum(
            abs(weight - initial)
            for weight, initial in zip(path.weights[0], (0.0, 0.0, 0.0, 1.0), strict=True)
        )
    )


def test_last_month_return_cannot_change_any_weight_decision() -> None:
    rows, gold = _monthly_fixture()
    candidate = registered_candidates()[7]
    original = build_strategy_path(rows, gold, candidate)
    changed_rows = list(rows)
    final = changed_rows[-1]
    changed_rows[-1] = MonthlyRow(
        final.date,
        final.price * 5.0,
        final.dividend,
        final.long_rate,
    )
    changed_gold = list(gold)
    changed_gold[-1] *= 7.0
    changed = build_strategy_path(changed_rows, changed_gold, candidate)

    assert changed.weights == original.weights
    assert changed.gross_factors[:-1] == pytest.approx(original.gross_factors[:-1])


def test_disabled_overlay_matches_incumbent_path() -> None:
    rows, gold = _monthly_fixture()
    never_stress = CandidateSpec(
        correlation_window_months=12,
        correlation_threshold=2.0,
        joint_weakness_lookback_months=3,
        defensive_action="cash",
    )
    path = build_strategy_path(rows, gold, never_stress)

    assert path.weights == path.incumbent_weights
    assert path.gross_factors == pytest.approx(path.incumbent_gross_factors)


def test_incumbent_path_exactly_reproduces_deployed_four_speed_average() -> None:
    rows, gold = _monthly_fixture()
    path = build_strategy_path(rows, gold, registered_candidates()[0])
    deployment_legs = [global_trend_factors(rows, gold, window=window) for window in (3, 6, 9, 12)]
    deployed = [sum(month) / len(month) for month in zip(*deployment_legs, strict=True)]

    assert path.incumbent_gross_factors == pytest.approx(deployed)


def test_stress_overlay_removes_stock_and_bond_without_leverage() -> None:
    rows, gold = _monthly_fixture()
    cash_candidate = next(
        candidate
        for candidate in registered_candidates()
        if candidate.correlation_window_months == 12
        and candidate.correlation_threshold == 0.0
        and candidate.joint_weakness_lookback_months == 3
        and candidate.defensive_action == "cash"
    )
    gold_candidate = CandidateSpec(12, 0.0, 3, "gold")
    cash_path = build_strategy_path(rows, gold, cash_candidate)
    gold_path = build_strategy_path(rows, gold, gold_candidate)
    stress_indexes = [index for index, active in enumerate(cash_path.stress_active) if active]

    assert stress_indexes
    for index in stress_indexes:
        assert cash_path.weights[index][0:2] == (0.0, 0.0)
        assert gold_path.weights[index][0:2] == (0.0, 0.0)
        removed = sum(cash_path.incumbent_weights[index][0:2])
        assert cash_path.weights[index][3] >= (
            cash_path.incumbent_weights[index][3] + removed - 1e-12
        )


def test_cost_model_charges_the_same_formula_to_both_paths() -> None:
    gross = [1.01, 0.99, 1.02]
    turnover = [0.5, 0.0, 0.25]

    candidate = apply_cost_model(gross, turnover, annual_fixed_bps=50, turnover_bps=10)
    incumbent = apply_cost_model(gross, turnover, annual_fixed_bps=50, turnover_bps=10)

    assert candidate == incumbent
    assert candidate[0] < gross[0]
    assert (
        apply_cost_model(gross, turnover, annual_fixed_bps=50, turnover_bps=50)[0] < (candidate[0])
    )


def test_evaluation_is_deterministic_time_separated_and_never_promotes() -> None:
    rows, gold = _monthly_fixture()
    contract = _contract()

    first = evaluate_regime_challenger(rows, gold, contract)
    second = evaluate_regime_challenger(rows, gold, contract)

    assert first == second
    assert first["candidate_count"] == 16
    assert first["split"]["development_end"] == "2006-12"
    assert first["split"]["embargo_month"] == "2007-01"
    assert first["split"]["holdout_start"] == "2007-02"
    assert first["split"]["overlap_months"] == 0
    assert first["multiplicity"]["resulting_research_family_count"] == 18
    assert first["multiplicity"]["program_false_acceptance_budget"] == 0.18
    assert first["safety"] == {
        "promotion_allowed": False,
        "orders_submitted": 0,
        "capital_changed": False,
    }
    concentration = first["post_result_activation_concentration"]
    assert concentration["diagnostic_status"] == "POST_RESULT_NOT_A_GATE"
    assert concentration["stress_months"] >= concentration["stress_episodes"]
    assert concentration["months_with_nonzero_gross_difference"] == (
        concentration["positive_difference_months"] + concentration["negative_difference_months"]
    )
    assert validate_report_payload(first, contract) is True


def test_result_validator_rejects_safety_or_identity_mutation() -> None:
    rows, gold = _monthly_fixture()
    contract = _contract()
    payload = evaluate_regime_challenger(rows, gold, contract)
    unsafe = copy.deepcopy(payload)
    unsafe["safety"]["promotion_allowed"] = True
    wrong_count = copy.deepcopy(payload)
    wrong_count["candidate_count"] = 15

    with pytest.raises(ValueError, match="safety"):
        validate_report_payload(unsafe, contract)
    with pytest.raises(ValueError, match="candidate_count"):
        validate_report_payload(wrong_count, contract)


def test_frozen_regime_candidate_starts_forward_observation_without_promotion() -> None:
    rows, gold = _monthly_fixture()
    contract = _contract()
    forward_contract = _forward_contract()

    payload = evaluate_regime_challenger(
        rows,
        gold,
        contract,
        forward_contract=forward_contract,
    )

    observation = payload["forward_observation"]
    assert observation["candidate_id"] == "regime-corr24-thr0p2-weak6-cash"
    assert observation["frozen_through"] == "2026-07"
    assert observation["n_obs"] == 0
    assert observation["active_return_psr"] is None
    assert observation["status"] == "OBSERVATION_WAIT"
    assert observation["promotion_allowed"] is False
    assert observation["orders_submitted"] == 0
    assert observation["capital_changed"] is False
    assert validate_report_payload(
        payload,
        contract,
        forward_contract=forward_contract,
    ) is True
