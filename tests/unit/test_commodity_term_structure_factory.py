from __future__ import annotations

import json
import math
from copy import deepcopy
from decimal import Decimal

import pytest

from auto_invest.analytics.commodity_term_structure_factory import (
    CommodityPolicy,
    CommoditySourceBundle,
    commodity_source_returns,
    commodity_target_weight,
    generate_commodity_candidates,
    parse_blackrock_performance,
    run_commodity_term_structure_factory,
    validate_live_commodity_evidence,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow


def _months(count: int = 240) -> list[str]:
    year, month = 2006, 8
    output = []
    for _ in range(count):
        output.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _bundle() -> CommoditySourceBundle:
    dates = _months()
    fund = [10_000.0]
    benchmark = [10_000.0]
    spot = [100.0]
    for index in range(1, len(dates)):
        spot_return = 0.003 + 0.012 * math.sin(index / 4)
        carry = 0.006 * math.sin(index / 10) + 0.001
        spot.append(spot[-1] * (1.0 + spot_return))
        benchmark.append(benchmark[-1] * (1.0 + spot_return + carry))
        fund.append(fund[-1] * (1.0 + spot_return + carry - 0.0006))
    return CommoditySourceBundle(
        dates=tuple(dates),
        fund_levels=tuple(fund),
        benchmark_levels=tuple(benchmark),
        spot_levels=tuple(spot),
        cash_rates=tuple(2.0 + (index % 12) / 20 for index in range(len(dates))),
        quality={"complete": True, "freshness_days": 25},
    )


def _rows() -> list[MonthlyRow]:
    return [
        MonthlyRow(
            month,
            price=100.0 * (1.006**index),
            dividend=2.0,
            long_rate=4.0 + math.sin(index / 8),
        )
        for index, month in enumerate(_months())
    ]


def _prior() -> dict:
    return {
        "audit_records": [
            {
                "candidate_id": f"prior-{index:03d}",
                "strategy_fingerprint": f"sha256:prior-{index:03d}",
                "status": "complete",
                "segment_sharpes": [0.1] * 10,
            }
            for index in range(656)
        ]
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


def _run(bundle: CommoditySourceBundle | None = None, prior: dict | None = None) -> dict:
    return run_commodity_term_structure_factory(
        _rows(),
        [400.0 * (1.004**index) for index in range(240)],
        bundle or _bundle(),
        prior_factory_payload=prior or _prior(),
        calibration_evidence=_calibration(),
        code_commit="abc123",
        timestamp_utc="2026-08-25T00:00:00Z",
    )


def test_blackrock_parser_uses_execution_ticker_and_rejects_mismatch() -> None:
    dates = [int(month.replace("-", "")[:6] + "28") for month in _months()]
    values = [str(10_000 + index) for index in range(240)]
    payload = {
        "aladdinFundTicker": "I-GSCITS",
        "productId": 239757,
        "pageScopeData": {"ticker": "GSG", "portfolioId": "239757"},
        "componentsByNameMap": {
            "performance": {
                "containersByNameMap": {
                    "chart": {
                        "dataPointsByNameMap": {
                            "performanceData": {"asOfDate": dates, "value": values},
                            "benchmarkData": {"asOfDate": dates, "value": values},
                        }
                    }
                }
            }
        },
    }
    fund, benchmark = parse_blackrock_performance(json.dumps(payload).encode())
    assert len(fund) == len(benchmark) == 240
    assert next(iter(fund)) == "2006-08-01"
    payload["pageScopeData"]["ticker"] = "WRONG"
    with pytest.raises(ValueError, match="ticker mismatch"):
        parse_blackrock_performance(json.dumps(payload).encode())


def test_candidate_family_is_frozen_unique_and_not_live_authorized() -> None:
    first = generate_commodity_candidates()
    second = generate_commodity_candidates()
    assert len(first) == 16
    assert [item.candidate_id for item in first] == [item.candidate_id for item in second]
    assert len({item.strategy_fingerprint for item in first}) == 16
    assert {item.policy.family for item in first} == {
        "carry_positive",
        "carry_momentum",
        "carry_rank",
        "defensive_carry",
    }
    assert all(item.as_dict()["live_expressible"] is False for item in first)


def test_target_weight_is_long_only_and_future_values_do_not_change_past() -> None:
    policy = CommodityPolicy("carry_positive", 3, Decimal("0.5"))
    before = commodity_target_weight(
        policy,
        carry_history=[0.01, 0.02, 0.03],
        benchmark_history=[100.0, 101.0, 102.0, 103.0],
        fund_return_history=[0.01, 0.01, 0.01],
    )
    after = commodity_target_weight(
        policy,
        carry_history=[0.01, 0.02, 0.03],
        benchmark_history=[100.0, 101.0, 102.0, 103.0],
        fund_return_history=[0.01, 0.01, 0.01],
    )
    assert before == after == Decimal("0.5")
    assert Decimal("0") <= before <= Decimal("1")


def test_term_structure_signal_subtracts_prior_known_cash_return() -> None:
    bundle = CommoditySourceBundle(
        dates=("2026-01-01", "2026-02-01"),
        fund_levels=(100.0, 100.2),
        benchmark_levels=(100.0, 100.2),
        spot_levels=(100.0, 100.0),
        cash_rates=(3.0, 3.0),
        quality={"complete": True},
    )
    _, carry, cash = commodity_source_returns(bundle)
    assert cash[0] == pytest.approx(1.0025)
    assert carry[0] == pytest.approx(-0.0005)


def test_factory_keeps_672_audit_trials_and_frozen_split() -> None:
    payload = _run()
    assert payload["candidate_count"] == 16
    assert payload["prior_trial_count"] == 656
    assert payload["global_audit_trial_count"] == 672
    assert payload["unique_trial_fingerprint_count"] == 672
    assert payload["development_selection"]["months"] == 96
    assert payload["holdout_confirmation"]["embargo_months"] == 1
    assert payload["holdout_confirmation"]["months"] == 142
    assert payload["decision"]["selected_deploy_config"] is None
    assert payload["decision"]["live_whitelist_authorized"] is False


def test_holdout_changes_cannot_reselect_development_winner() -> None:
    original = _bundle()
    first = _run(original)
    fund = list(original.fund_levels)
    benchmark = list(original.benchmark_levels)
    spot = list(original.spot_levels)
    for index in range(98, len(fund)):
        fund[index] *= 1.0 + 0.2 * math.sin(index)
        benchmark[index] *= 1.0 + 0.1 * math.cos(index)
        spot[index] *= 1.0 + 0.1 * math.sin(index / 2)
    changed = CommoditySourceBundle(
        dates=original.dates,
        fund_levels=tuple(fund),
        benchmark_levels=tuple(benchmark),
        spot_levels=tuple(spot),
        cash_rates=original.cash_rates,
        quality=original.quality,
    )
    second = _run(changed)
    assert (
        first["development_selection"]["selected_candidate_id"]
        == second["development_selection"]["selected_candidate_id"]
    )


def test_missing_prior_or_bad_data_fails_common_gate() -> None:
    prior = _prior()
    prior["audit_records"].pop()
    payload = _run(prior=prior)
    gates = {gate["gate_id"]: gate for gate in payload["decision"]["gates"]}
    assert gates["prior_audit_complete"]["passed"] is False
    assert payload["decision"]["research_canary_eligible"] is False

    bundle = _bundle()
    stale = deepcopy(bundle.quality)
    stale["complete"] = False
    stale_payload = _run(
        CommoditySourceBundle(
            dates=bundle.dates,
            fund_levels=bundle.fund_levels,
            benchmark_levels=bundle.benchmark_levels,
            spot_levels=bundle.spot_levels,
            cash_rates=bundle.cash_rates,
            quality=stale,
        )
    )
    stale_gates = {gate["gate_id"]: gate for gate in stale_payload["decision"]["gates"]}
    assert stale_gates["commodity_data_complete"]["passed"] is False


def test_live_validator_rejects_non_live_and_non_whitelisted_evidence() -> None:
    payload = _run()
    payload["decision"]["verdict"] = "NO_FACTORY_EDGE"
    payload["decision"]["research_canary_eligible"] = False
    with pytest.raises(ValueError, match="not live-grade"):
        validate_live_commodity_evidence(payload, code_commit="abc123")

    payload["decision"]["verdict"] = "FACTORY_EDGE"
    payload["decision"]["research_canary_eligible"] = True
    with pytest.raises(ValueError, match="not authorized"):
        validate_live_commodity_evidence(payload, code_commit="abc123")
