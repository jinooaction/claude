from __future__ import annotations

import math
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest

from auto_invest.analytics.commodity_supply_demand_factory import (
    EIA_SERIES,
    CommoditySupplyDemandBundle,
    CommoditySupplyDemandPolicy,
    generate_supply_demand_candidates,
    parse_eia_weekly_series,
    run_commodity_supply_demand_factory,
    supply_demand_target_weight,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow


def _months(count: int = 230) -> list[str]:
    year, month = 2007, 7
    output: list[str] = []
    for _ in range(count):
        output.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _bundle() -> CommoditySupplyDemandBundle:
    dates = _months()
    fund = [10_000.0]
    for index in range(1, len(dates)):
        fund.append(fund[-1] * (1.0 + 0.005 + 0.025 * math.sin(index / 6)))
    inventory = tuple(math.sin(index / 8) for index in range(len(dates)))
    demand = tuple(math.cos(index / 9) for index in range(len(dates)))
    refinery = tuple(math.sin(index / 7 + 1) for index in range(len(dates)))
    return CommoditySupplyDemandBundle(
        dates=tuple(dates),
        fund_levels=tuple(fund),
        cash_rates=tuple(2.0 + index % 12 / 20 for index in range(len(dates))),
        inventory_signals={52: inventory, 104: inventory},
        demand_signals={52: demand, 104: demand},
        refinery_signals={52: refinery, 104: refinery},
        quality={"complete": True, "freshness_days": 11},
    )


def _rows() -> list[MonthlyRow]:
    return [
        MonthlyRow(month, 100.0 * (1.006**index), 2.0, 4.0 + math.sin(index / 8))
        for index, month in enumerate(_months())
    ]


def _prior() -> dict:
    return {
        "audit_records": [
            {
                "candidate_id": f"prior-{index:03d}",
                "strategy_fingerprint": f"sha256:prior-{index:03d}",
                "status": "complete",
            }
            for index in range(688)
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


def _controls(valid: bool = True) -> dict:
    return {
        "verdict": "FULL_GATE_CONTROLS_VALID" if valid else "FULL_GATE_CONTROLS_FAILED",
        "promotion_control_passed": valid,
        "code_commit": "abc123",
        "control_fingerprint": "sha256:full-controls",
    }


def _run(bundle: CommoditySupplyDemandBundle | None = None, controls: dict | None = None) -> dict:
    return run_commodity_supply_demand_factory(
        _rows(),
        [400.0 * (1.004**index) for index in range(230)],
        bundle or _bundle(),
        prior_factory_payload=_prior(),
        calibration_evidence=_calibration(),
        full_gate_controls=controls or _controls(),
        code_commit="abc123",
        timestamp_utc="2026-08-25T00:00:00Z",
    )


def test_eia_parser_requires_fixed_identity_and_five_day_lag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSheet:
        nrows = 1400

        @staticmethod
        def cell_value(row: int, column: int) -> object:
            if (row, column) == (1, 1):
                return "WCRFPUS2"
            if row >= 3 and column == 0:
                return 45_000 + row
            if row >= 3 and column == 1:
                return 8_000 + row
            return ""

    class FakeWorkbook:
        datemode = 0

        @staticmethod
        def sheet_by_name(name: str) -> FakeSheet:
            assert name == "Data 1"
            return FakeSheet()

    monkeypatch.setattr(
        "auto_invest.analytics.commodity_supply_demand_factory.xlrd.open_workbook",
        lambda **_: FakeWorkbook(),
    )
    parsed = parse_eia_weekly_series(b"fixed-eia", "WCRFPUS2")
    assert len(parsed) == 1397
    assert parsed[0].available_date == parsed[0].period_end + timedelta(days=5)
    with pytest.raises(ValueError, match="identity"):
        parse_eia_weekly_series(b"fixed-eia", "WCESTUS1")


def test_candidate_family_and_target_rules_are_frozen() -> None:
    candidates = generate_supply_demand_candidates()
    assert len(candidates) == 16
    assert len({item.candidate_id for item in candidates}) == 16
    assert len({item.strategy_fingerprint for item in candidates}) == 16
    assert set(EIA_SERIES) == {"WCESTUS1", "WCRFPUS2", "WGIRIUS2", "WRPUPUS2"}
    assert {item.policy.family for item in candidates} == {
        "inventory_draw",
        "demand_growth",
        "refinery_pull",
        "synchronized_balance",
    }
    policy = CommoditySupplyDemandPolicy("synchronized_balance", 52, Decimal("0.5"))
    assert supply_demand_target_weight(policy, 1.0, 1.0, 1.0) == Decimal("0.5")
    assert supply_demand_target_weight(policy, 1.0, -1.0, 1.0) == Decimal("0")


def test_factory_keeps_704_trials_and_untouched_holdout() -> None:
    first = _run()
    assert first["candidate_count"] == 16
    assert first["prior_trial_count"] == 688
    assert first["global_audit_trial_count"] == 704
    assert first["unique_trial_fingerprint_count"] == 704
    assert first["development_selection"]["months"] == 96
    assert first["holdout_confirmation"]["embargo_months"] == 1
    assert first["holdout_confirmation"]["months"] == 132
    assert first["decision"]["live_whitelist_authorized"] is False
    assert "diagnostic_classification" in first["decision"]
    original = _bundle()
    changed = deepcopy(original)
    fund = list(original.fund_levels)
    for index in range(98, len(fund)):
        fund[index] *= 1.0 + 0.2 * math.sin(index)
    object.__setattr__(changed, "fund_levels", tuple(fund))
    second = _run(changed)
    assert (
        first["development_selection"]["selected_candidate_id"]
        == second["development_selection"]["selected_candidate_id"]
    )


def test_full_controls_fail_closed_and_source_has_no_broker_boundary() -> None:
    failed = _run(controls=_controls(False))
    gates = {row["gate_id"]: row for row in failed["decision"]["gates"]}
    assert gates["full_gate_controls"]["passed"] is False
    assert failed["decision"]["research_canary_eligible"] is False
    from pathlib import Path

    source = Path("src/auto_invest/analytics/commodity_supply_demand_factory.py").read_text()
    assert "auto_invest.brokers" not in source
    assert "KisBroker" not in source
