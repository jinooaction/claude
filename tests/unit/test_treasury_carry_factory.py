from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.analytics.treasury_carry_factory import (
    EXPECTED_CANDIDATES,
    EXPECTED_GLOBAL_AUDIT_TRIALS,
    NO_FACTORY_EDGE,
    TreasuryCurveSnapshot,
    build_treasury_curve_snapshots,
    generate_treasury_candidates,
    run_treasury_carry_factory,
    validate_live_treasury_evidence,
)
from auto_invest.config.rules import TreasuryCarryPolicyConfig
from auto_invest.market_data.public_data import SeriesPoint
from auto_invest.strategy.rebalance import treasury_target_weights


def _monthly_rows(count: int = 444) -> list[MonthlyRow]:
    rows: list[MonthlyRow] = []
    year, month = 1990, 1
    for index in range(count):
        rows.append(
            MonthlyRow(
                date(year, month, 1).isoformat(),
                price=100 * (1.006**index),
                dividend=2.0,
                long_rate=4.0 + (index % 24 - 12) / 20,
            )
        )
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return rows


def _snapshots(rows: list[MonthlyRow]) -> list[TreasuryCurveSnapshot]:
    histories = {symbol: [] for symbol in ("SGOV", "SHY", "IEI", "IEF", "TLT")}
    snapshots: list[TreasuryCurveSnapshot] = []
    for index, row in enumerate(rows):
        values = {
            "SGOV": Decimal("3.0") + Decimal(index % 12) / Decimal("20"),
            "SHY": Decimal("3.2") + Decimal(index % 18) / Decimal("20"),
            "IEI": Decimal("3.5") + Decimal(index % 24) / Decimal("20"),
            "IEF": Decimal("3.8") + Decimal(index % 30) / Decimal("20"),
            "TLT": Decimal("4.1") + Decimal(index % 36) / Decimal("20"),
        }
        for symbol, value in values.items():
            histories[symbol].append(value)
        snapshots.append(
            TreasuryCurveSnapshot(
                as_of_date=row.date,
                yields=values,
                observation_dates={symbol: row.date for symbol in values},
                yield_history={symbol: tuple(values) for symbol, values in histories.items()},
                complete=True,
                fresh=True,
            )
        )
    return snapshots


def _prior_ledger() -> list[dict]:
    return [
        {
            "candidate_id": f"factory-prior-{index:03d}",
            "strategy_fingerprint": f"sha256:price-{index:03d}",
            "status": "complete",
            "sharpe_25bps": 0.1 + index / 10_000,
            "segment_sharpes": [0.1 + segment / 100 for segment in range(10)],
        }
        for index in range(256)
    ]


def _prior_factory() -> dict:
    return {
        "exploratory_replay": [
            {
                "candidate_id": f"exploratory-prior-{index:03d}",
                "strategy_fingerprint": f"sha256:explore-{index:03d}",
                "status": "EXPLORATORY_REJECTED",
                "sharpe_25bps": 0.2,
                "segment_sharpes": [0.2] * 10,
            }
            for index in range(192)
        ],
        "trial_records": [
            {
                "candidate_id": f"macro-prior-{index:03d}",
                "strategy_fingerprint": f"sha256:macro-{index:03d}",
                "status": "complete",
                "sharpe_25bps": 0.3,
                "segment_sharpes": [0.3] * 10,
            }
            for index in range(64)
        ],
    }


def _calibration(code_commit: str = "abc123") -> dict:
    return {
        "gate_version": "2.0",
        "verdict": "CALIBRATED",
        "code_commit": code_commit,
        "scenario": {"repetitions": 500},
        "revised": {"false_acceptance_rate": 0.036, "detection_rate": 0.834},
        "thresholds": {
            "development_dsr_diagnostic_min": 0.95,
            "development_pbo_diagnostic_max": 0.10,
            "holdout_psr_min": 0.95,
        },
    }


def test_candidate_grammar_is_frozen_unique_and_deterministic() -> None:
    first = generate_treasury_candidates()
    second = generate_treasury_candidates()
    assert len(first) == EXPECTED_CANDIDATES
    assert [candidate.candidate_id for candidate in first] == [
        candidate.candidate_id for candidate in second
    ]
    assert len({candidate.strategy_fingerprint for candidate in first}) == 64
    assert {candidate.policy.family for candidate in first} == {
        "carry_roll",
        "carry_rate_trend",
        "defensive_curve",
        "curve_barbell",
    }
    assert all(
        sum(candidate.policy.family == family for candidate in first) == 16
        for family in {candidate.policy.family for candidate in first}
    )


def test_shared_treasury_policy_is_long_only_and_stale_fails_closed() -> None:
    policy = TreasuryCarryPolicyConfig(
        family="carry_rate_trend",
        max_maturity_years=30,
        lookback_months=3,
        top_n=2,
        signal_strength=Decimal("1.0"),
    )
    snapshot = _snapshots(_monthly_rows(14))[-1].as_dict(include_history=True)
    snapshot["as_of_date"] = "2026-08-23"
    weights = treasury_target_weights(policy=policy, snapshot=snapshot)
    assert set(weights) <= {"SGOV", "SHY", "IEI", "IEF", "TLT"}
    assert len(weights) == 2
    assert sum(weights.values()) == Decimal("1.000000")
    assert all(weight >= 0 for weight in weights.values())
    snapshot["fresh"] = False
    with pytest.raises(ValueError, match="stale"):
        treasury_target_weights(policy=policy, snapshot=snapshot)


def test_barbell_signal_strength_changes_actual_target_weights() -> None:
    snapshot = _snapshots(_monthly_rows(14))[-1].as_dict(include_history=True)
    weak = TreasuryCarryPolicyConfig(
        family="curve_barbell",
        max_maturity_years=30,
        lookback_months=3,
        top_n=2,
        signal_strength=Decimal("0.5"),
    )
    strong = weak.model_copy(update={"signal_strength": Decimal("1.0")})
    weak_weights = treasury_target_weights(policy=weak, snapshot=snapshot)
    strong_weights = treasury_target_weights(policy=strong, snapshot=snapshot)
    assert weak_weights != strong_weights
    assert sum(weak_weights.values()) == Decimal("1.000000")
    assert sum(strong_weights.values()) == Decimal("1.000000")


def test_point_in_time_snapshot_does_not_consume_future_observation() -> None:
    series = {
        series_id: [
            SeriesPoint(date="2020-01-31", value=Decimal("2")),
            SeriesPoint(date="2020-02-03", value=Decimal("9")),
        ]
        for series_id in ("DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30")
    }
    snapshot = build_treasury_curve_snapshots(["2020-02-01"], series=series)[0]
    assert snapshot.complete is True
    assert set(snapshot.yields.values()) == {Decimal("2")}
    assert set(snapshot.observation_dates.values()) == {"2020-01-31"}


def test_factory_accounts_for_exactly_576_trials_and_fails_closed() -> None:
    rows = _monthly_rows()
    payload = run_treasury_carry_factory(
        rows,
        [400 * (1.004**index) for index in range(len(rows))],
        _snapshots(rows),
        treasury_data_quality={"complete": True},
        prior_trial_records=_prior_ledger(),
        prior_factory_payload=_prior_factory(),
        calibration_evidence=_calibration(),
        code_commit="abc123",
        timestamp_utc="2026-08-23T00:00:00Z",
    )
    assert payload["prior_trial_count"] == 512
    assert payload["current_trial_count"] == 64
    assert payload["global_audit_trial_count"] == EXPECTED_GLOBAL_AUDIT_TRIALS
    assert payload["multiplicity_trial_count"] == 64
    assert payload["family_raw_trial_count"] == 64
    assert Decimal("1") <= Decimal(payload["family_effective_trial_count"]) <= Decimal("64")
    assert payload["unique_trial_fingerprint_count"] == EXPECTED_GLOBAL_AUDIT_TRIALS
    assert payload["decision"]["verdict"] == NO_FACTORY_EDGE
    assert payload["decision"]["selected_candidate_id"] is None
    assert payload["decision"]["selected_deploy_config"] is None


def test_missing_prior_or_duplicate_fingerprint_cannot_authorize_canary() -> None:
    rows = _monthly_rows()
    ledger = _prior_ledger()[:-1]
    prior = _prior_factory()
    prior["trial_records"][1]["strategy_fingerprint"] = prior["trial_records"][0][
        "strategy_fingerprint"
    ]
    payload = run_treasury_carry_factory(
        rows,
        [400 * (1.004**index) for index in range(len(rows))],
        _snapshots(rows),
        treasury_data_quality={"complete": True},
        prior_trial_records=ledger,
        prior_factory_payload=prior,
        calibration_evidence=_calibration(code_commit="unknown"),
    )
    gates = {gate["gate_id"]: gate for gate in payload["decision"]["gates"]}
    assert gates["prior_audit_complete"]["passed"] is False
    assert gates["global_audit_trials"]["passed"] is False
    assert gates["unique_audit_fingerprints"]["passed"] is False
    assert payload["decision"]["research_canary_eligible"] is False


def test_prior_families_do_not_change_current_family_statistics() -> None:
    rows = _monthly_rows()
    base_kwargs = {
        "rows": rows,
        "gold_levels": [400 * (1.004**index) for index in range(len(rows))],
        "snapshots": _snapshots(rows),
        "treasury_data_quality": {"complete": True},
        "prior_factory_payload": _prior_factory(),
        "calibration_evidence": _calibration(),
        "code_commit": "abc123",
    }
    first = run_treasury_carry_factory(
        prior_trial_records=_prior_ledger(),
        **base_kwargs,
    )
    changed_prior = _prior_ledger()
    for record in changed_prior:
        record["sharpe_25bps"] += 100
        record["segment_sharpes"] = [-100.0, 100.0] * 5
    second = run_treasury_carry_factory(
        prior_trial_records=changed_prior,
        **base_kwargs,
    )
    assert first["development_selection"] == second["development_selection"]
    assert first["family_effective_trial_count"] == second["family_effective_trial_count"]
    assert first["decision"]["pbo"] == second["decision"]["pbo"]


def test_holdout_changes_cannot_reselect_development_winner() -> None:
    rows = _monthly_rows()
    original = _snapshots(rows)
    altered: list[TreasuryCurveSnapshot] = []
    for index, snapshot in enumerate(original):
        if snapshot.as_of_date < "2007-01-01":
            altered.append(snapshot)
            continue
        shift = Decimal("8") if index % 2 else Decimal("-2")
        altered.append(
            replace(
                snapshot,
                yields={
                    symbol: max(Decimal("0.1"), value + shift)
                    for symbol, value in snapshot.yields.items()
                    if value is not None
                },
            )
        )
    kwargs = {
        "rows": rows,
        "gold_levels": [400 * (1.004**index) for index in range(len(rows))],
        "treasury_data_quality": {"complete": True},
        "prior_trial_records": _prior_ledger(),
        "prior_factory_payload": _prior_factory(),
        "calibration_evidence": _calibration(),
        "code_commit": "abc123",
    }
    first = run_treasury_carry_factory(snapshots=original, **kwargs)
    second = run_treasury_carry_factory(snapshots=altered, **kwargs)
    assert (
        first["development_selection"]["selected_candidate_id"]
        == second["development_selection"]["selected_candidate_id"]
    )
    assert first["decision"]["objective"] == "diversifier"
    gates = {gate["gate_id"]: gate for gate in first["decision"]["gates"]}
    assert gates["blend_sharpe_improvement"]["blocking"] is True
    assert gates["standalone_sharpe_diagnostic"]["blocking"] is False


def test_live_evidence_rejects_no_winner_and_accepts_matching_all_pass() -> None:
    with pytest.raises(ValueError, match="no eligible winner"):
        validate_live_treasury_evidence(
            {
                "gate_version": "2.0",
                "timestamp_utc": "2026-08-23T00:00:00Z",
                "decision": {"verdict": NO_FACTORY_EDGE},
            },
            candidate_id="candidate",
            strategy_fingerprint="sha256:x",
            now=datetime(2026, 8, 23, tzinfo=UTC),
        )

    snapshot = _snapshots(_monthly_rows(14))[-1].as_dict(include_history=True)
    snapshot["as_of_date"] = "2026-08-23"
    payload = {
        "gate_version": "2.0",
        "timestamp_utc": "2026-08-23T00:00:00Z",
        "code_commit": "abc",
        "treasury_data_fingerprint": "sha256:data",
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_candidate_id": "candidate",
            "selected_strategy_fingerprint": "sha256:x",
            "gates": [{"gate_id": "all", "passed": True, "blocking": True}],
        },
        "research_live_parity": {"target_weights_digest": "sha256:weights"},
        "live_treasury_evidence": {
            "candidate_id": "candidate",
            "strategy_fingerprint": "sha256:x",
            "data_fingerprint": "sha256:data",
            "code_commit": "abc",
            "target_weights_digest": "sha256:weights",
            "fresh": True,
            "complete": True,
            "latest_snapshot": snapshot,
        },
    }
    assert (
        validate_live_treasury_evidence(
            payload,
            candidate_id="candidate",
            strategy_fingerprint="sha256:x",
            now=datetime(2026, 8, 23, tzinfo=UTC),
        )
        == snapshot
    )
