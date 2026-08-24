from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

import pytest

from auto_invest.analytics.commodity_positioning_factory import (
    CFTC_CONTRACTS,
    CommodityPositioningBundle,
    CommodityPositioningPolicy,
    generate_positioning_candidates,
    parse_cftc_positions,
    parse_eia_inventory,
    positioning_target_weight,
    run_commodity_positioning_factory,
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


def _bundle() -> CommodityPositioningBundle:
    dates = _months()
    fund = [10_000.0]
    for index in range(1, len(dates)):
        fund.append(fund[-1] * (1.0 + 0.006 + 0.02 * math.sin(index / 5)))
    managed = tuple(math.sin(index / 8) for index in range(len(dates)))
    producer = tuple(math.cos(index / 10) for index in range(len(dates)))
    inventory = tuple(math.sin(index / 6 + 1) for index in range(len(dates)))
    return CommodityPositioningBundle(
        dates=tuple(dates),
        fund_levels=tuple(fund),
        cash_rates=tuple(2.0 + index % 12 / 20 for index in range(len(dates))),
        managed_signals={26: managed, 52: managed},
        producer_signals={26: producer, 52: producer},
        inventory_signals={26: inventory, 52: inventory},
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
            for index in range(672)
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
        "verdict": "REAL_WORLD_CONTROLS_VALID" if valid else "REAL_WORLD_CONTROLS_FAILED",
        "promotion_control_passed": valid,
        "code_commit": "abc123",
        "control_fingerprint": "sha256:controls",
    }


def _run(bundle: CommodityPositioningBundle | None = None, controls: dict | None = None) -> dict:
    return run_commodity_positioning_factory(
        _rows(),
        [400.0 * (1.004**index) for index in range(230)],
        bundle or _bundle(),
        prior_factory_payload=_prior(),
        calibration_evidence=_calibration(),
        real_world_controls=controls or _controls(),
        code_commit="abc123",
        timestamp_utc="2026-08-25T00:00:00Z",
    )


def test_cftc_parser_requires_fixed_contracts_and_publication_lag() -> None:
    report = date(2026, 8, 4)
    rows = []
    for code, name in CFTC_CONTRACTS.items():
        rows.append(
            {
                "cftc_contract_market_code": code,
                "contract_market_name": name,
                "report_date_as_yyyy_mm_dd": report.isoformat() + "T00:00:00.000",
                "open_interest_all": "1000",
                "m_money_positions_long_all": "300",
                "m_money_positions_short_all": "200",
                "prod_merc_positions_long": "100",
                "prod_merc_positions_short": "400",
            }
        )
    parsed = parse_cftc_positions(json.dumps(rows).encode())
    assert len(parsed) == 12
    assert all(item.available_date == report + timedelta(days=3) for item in parsed)
    rows.pop()
    with pytest.raises(ValueError, match="fixed contract coverage"):
        parse_cftc_positions(json.dumps(rows).encode())


def test_eia_parser_requires_fixed_series_and_publication_lag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSheet:
        nrows = 1000

        @staticmethod
        def cell_value(row: int, column: int) -> object:
            if (row, column) == (1, 1):
                return "WCESTUS1"
            if row >= 3 and column == 0:
                return 45_000 + row
            if row >= 3 and column == 1:
                return 400_000 + row
            return ""

    class FakeWorkbook:
        datemode = 0

        @staticmethod
        def sheet_by_name(name: str) -> FakeSheet:
            assert name == "Data 1"
            return FakeSheet()

    monkeypatch.setattr(
        "auto_invest.analytics.commodity_positioning_factory.xlrd.open_workbook",
        lambda **_: FakeWorkbook(),
    )

    parsed = parse_eia_inventory(b"fixed-eia-workbook")

    assert len(parsed) == 997
    assert parsed[0].available_date == parsed[0].period_end + timedelta(days=5)


def test_candidate_family_and_target_rules_are_frozen() -> None:
    candidates = generate_positioning_candidates()
    assert len(candidates) == 16
    assert len({item.candidate_id for item in candidates}) == 16
    assert len({item.strategy_fingerprint for item in candidates}) == 16
    assert {item.policy.family for item in candidates} == {
        "managed_money_trend",
        "producer_scarcity",
        "inventory_tightness",
        "positioning_inventory_confirmation",
    }
    policy = CommodityPositioningPolicy("positioning_inventory_confirmation", 26, Decimal("0.5"))
    assert positioning_target_weight(policy, 1.0, -1.0, 1.0) == Decimal("0.5")
    assert positioning_target_weight(policy, -1.0, 1.0, 1.0) == Decimal("0")


def test_factory_keeps_688_trials_and_untouched_holdout() -> None:
    payload = _run()
    assert payload["candidate_count"] == 16
    assert payload["prior_trial_count"] == 672
    assert payload["global_audit_trial_count"] == 688
    assert payload["unique_trial_fingerprint_count"] == 688
    assert payload["development_selection"]["months"] == 96
    assert payload["holdout_confirmation"]["embargo_months"] == 1
    assert payload["holdout_confirmation"]["months"] == 132
    assert payload["decision"]["selected_deploy_config"] is None
    assert payload["decision"]["live_whitelist_authorized"] is False


def test_holdout_changes_do_not_reselect_and_controls_fail_closed() -> None:
    original = _bundle()
    first = _run(original)
    fund = list(original.fund_levels)
    for index in range(98, len(fund)):
        fund[index] *= 1.0 + 0.2 * math.sin(index)
    changed = deepcopy(original)
    object.__setattr__(changed, "fund_levels", tuple(fund))
    second = _run(changed)
    assert (
        first["development_selection"]["selected_candidate_id"]
        == second["development_selection"]["selected_candidate_id"]
    )
    failed = _run(controls=_controls(False))
    gates = {row["gate_id"]: row for row in failed["decision"]["gates"]}
    assert gates["real_world_gate_controls"]["passed"] is False
    assert failed["decision"]["research_canary_eligible"] is False


def test_factory_source_contains_no_broker_boundary() -> None:
    from pathlib import Path

    source = Path("src/auto_invest/analytics/commodity_positioning_factory.py").read_text()
    assert "auto_invest.brokers" not in source
    assert "KisBroker" not in source
