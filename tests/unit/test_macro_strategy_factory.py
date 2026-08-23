from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from auto_invest.analytics.macro_strategy_factory import (
    EXPECTED_CANDIDATES,
    EXPECTED_EXPLORATORY_TRIALS,
    NO_FACTORY_EDGE,
    generate_exploratory_candidates,
    generate_macro_candidates,
    run_macro_strategy_factory,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.config.rules import MacroPolicyConfig
from auto_invest.market_data.macro_regime import MacroSnapshot
from auto_invest.strategy.rebalance import macro_target_weights


def _snapshot(as_of: str) -> MacroSnapshot:
    return MacroSnapshot(
        as_of_date=as_of,
        yield_spread_10y2y=Decimal("-0.1"),
        curve_history=tuple([Decimal("-0.3")] * 60),
        cpi_yoy=Decimal("4.2"),
        cpi_direction_3m=Decimal("0.2"),
        cpi_direction_6m=Decimal("0.4"),
        cpi_available_date=as_of,
        sahm_realtime=Decimal("0.6"),
        sahm_direction_3m=Decimal("0.1"),
        sahm_direction_6m=Decimal("0.2"),
        sahm_available_date=as_of,
        vix_close=Decimal("30"),
        vix_history=tuple([Decimal("30")] * 20),
        source_freshness_days={"yield_curve": 1, "vix": 1, "cpi": 10, "sahm_realtime": 10},
        cross_check_status="PASS",
        complete=True,
        fresh=True,
    )


def _monthly_rows(start_year: int = 1990, count: int = 372) -> list[MonthlyRow]:
    rows: list[MonthlyRow] = []
    year, month = start_year, 1
    for index in range(count):
        rows.append(
            MonthlyRow(
                date(year, month, 1).isoformat(),
                price=100 * (1.006**index),
                dividend=2.0,
                long_rate=4.0,
            )
        )
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return rows


def _prior_records(count: int = 256) -> list[dict]:
    return [
        {
            "candidate_id": f"factory-prior-{index:03d}",
            "strategy_fingerprint": f"sha256:prior-{index:03d}",
            "status": "complete",
            "sharpe_25bps": 0.1 + index / 10_000,
            "segment_sharpes": [0.1 + segment / 100 for segment in range(10)],
        }
        for index in range(count)
    ]


def test_official_and_exploratory_grammars_are_deterministic_and_complete() -> None:
    first = generate_macro_candidates()
    second = generate_macro_candidates()
    assert len(first) == EXPECTED_CANDIDATES
    assert [candidate.candidate_id for candidate in first] == [
        candidate.candidate_id for candidate in second
    ]
    assert {candidate.family for candidate in first} == {
        "curve_cycle",
        "inflation_direction",
        "labor_growth_shock",
        "vix_shock_recovery",
    }
    assert all(
        sum(candidate.family == family for candidate in first) == 16
        for family in {candidate.family for candidate in first}
    )
    explorers = generate_exploratory_candidates()
    assert len(explorers) == EXPECTED_EXPLORATORY_TRIALS
    assert len({candidate.candidate_id for candidate in explorers}) == len(explorers)


def test_shared_macro_policy_is_long_only_and_rejects_stale_snapshot() -> None:
    policy = MacroPolicyConfig(
        family="curve_cycle",
        base_portfolio="equal_3asset",
        threshold=Decimal("0"),
        confirmation_days=20,
        release_threshold_pp=Decimal("0.25"),
        tilt_pct=Decimal("20"),
    )
    snapshot = _snapshot("2020-01-01").as_dict(include_history=True)
    weights = macro_target_weights(
        base_weights={
            "SPY": Decimal("0.333334"),
            "IEF": Decimal("0.333333"),
            "GLD": Decimal("0.333333"),
        },
        policy=policy,
        snapshot=snapshot,
    )
    assert weights == {
        "SPY": Decimal("0.133334"),
        "IEF": Decimal("0.483333"),
        "GLD": Decimal("0.383333"),
    }
    snapshot["fresh"] = False
    with pytest.raises(ValueError, match="incomplete or stale"):
        macro_target_weights(base_weights=weights, policy=policy, snapshot=snapshot)


def test_factory_accounts_for_exactly_512_trials_and_fails_closed() -> None:
    rows = _monthly_rows()
    snapshots = [_snapshot(row.date) for row in rows[:-1]]
    quality = {
        "complete": True,
        "cross_check_status": "PASS",
        "series": {"SAHMREALTIME": {"complete": True}},
    }
    payload = run_macro_strategy_factory(
        rows,
        [100 * (1.004**index) for index in range(len(rows))],
        snapshots,
        macro_data_quality=quality,
        prior_trial_records=_prior_records(),
        code_commit="abc123",
        timestamp_utc="2026-08-23T00:00:00Z",
    )

    assert payload["production_trial_count"] == 256
    assert payload["exploratory_trial_count"] == 192
    assert payload["current_trial_count"] == 64
    assert payload["multiplicity_trial_count"] == 512
    assert payload["decision"]["verdict"] == NO_FACTORY_EDGE
    assert payload["decision"]["selected_candidate_id"] is None


def test_factory_missing_prior_replay_cannot_authorize_canary() -> None:
    rows = _monthly_rows()
    payload = run_macro_strategy_factory(
        rows,
        [100 * (1.004**index) for index in range(len(rows))],
        [_snapshot(row.date) for row in rows[:-1]],
        macro_data_quality={
            "complete": True,
            "series": {"SAHMREALTIME": {"complete": True}},
        },
        prior_trial_records=_prior_records(255),
    )
    gates = {gate["gate_id"]: gate for gate in payload["decision"]["gates"]}
    assert gates["production_replay_complete"]["passed"] is False
    assert gates["multiplicity_trials"]["passed"] is False
    assert payload["decision"]["research_canary_eligible"] is False


def test_factory_duplicate_fingerprint_cannot_inflate_trial_count() -> None:
    rows = _monthly_rows()
    prior_records = _prior_records()
    prior_records[1]["strategy_fingerprint"] = prior_records[0]["strategy_fingerprint"]
    payload = run_macro_strategy_factory(
        rows,
        [100 * (1.004**index) for index in range(len(rows))],
        [_snapshot(row.date) for row in rows[:-1]],
        macro_data_quality={
            "complete": True,
            "series": {"SAHMREALTIME": {"complete": True}},
        },
        prior_trial_records=prior_records,
    )

    gates = {gate["gate_id"]: gate for gate in payload["decision"]["gates"]}
    assert payload["multiplicity_trial_count"] == 512
    assert payload["unique_trial_fingerprint_count"] == 511
    assert gates["unique_trial_fingerprints"]["passed"] is False
    assert payload["decision"]["research_canary_eligible"] is False
