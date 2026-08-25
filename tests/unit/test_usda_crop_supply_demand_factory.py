from __future__ import annotations

import math
from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.analytics.usda_crop_supply_demand_factory import (
    CropSupplyDemandBundle,
    CropSupplyDemandPolicy,
    WasdeCropObservation,
    WasdeWorkbookRef,
    actual_holdout_psr_power,
    build_revision_snapshots,
    crop_target_gold_weight,
    generate_crop_supply_demand_candidates,
    parse_wasde_index_pages,
    parse_wasde_workbook,
    run_usda_crop_supply_demand_factory,
)


def _months(count: int = 193) -> list[str]:
    year, month = 2010, 7
    output: list[str] = []
    for _ in range(count):
        output.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _bundle() -> CropSupplyDemandBundle:
    dates = _months()
    revisions = {
        horizon: {
            "corn": tuple(math.sin(index / 5) for index in range(len(dates))),
            "wheat": tuple(math.cos(index / 7) for index in range(len(dates))),
            "soybeans": tuple(math.sin(index / 9 + 1) for index in range(len(dates))),
        }
        for horizon in (1, 3)
    }
    return CropSupplyDemandBundle(
        dates=tuple(dates),
        cash_rates=tuple(2.0 + index % 12 / 20 for index in range(len(dates))),
        revisions=revisions,
        latest_revisions={
            horizon: {crop: values[-1] for crop, values in crops.items()}
            for horizon, crops in revisions.items()
        },
        latest_release_date=date(2026, 8, 12),
        quality={"complete": True, "release_count": 193},
    )


def _rows() -> list[MonthlyRow]:
    return [
        MonthlyRow(month, 100.0 * (1.006**index), 2.0, 4.0 + math.sin(index / 8))
        for index, month in enumerate(_months())
    ]


def _prior() -> dict:
    return {
        "supply_demand_data_fingerprint": "sha256:prior-supply-demand-data",
        "audit_records": [
            {
                "candidate_id": f"prior-{index:03d}",
                "strategy_fingerprint": f"sha256:prior-{index:03d}",
                "status": "complete",
            }
            for index in range(704)
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


def _run(bundle: CropSupplyDemandBundle | None = None, controls: dict | None = None) -> dict:
    return run_usda_crop_supply_demand_factory(
        _rows(),
        [400.0 * (1.004**index) for index in range(193)],
        bundle or _bundle(),
        prior_factory_payload=_prior(),
        calibration_evidence=_calibration(),
        full_gate_controls=controls or _controls(),
        code_commit="abc123",
        timestamp_utc="2026-08-25T00:00:00Z",
    )


def _advance_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 12)


def test_index_parser_requires_preregistered_point_in_time_depth() -> None:
    release = date(2010, 7, 12)
    rows: list[str] = []
    for index in range(190):
        rows.append(
            f'<tr><time datetime="{release.isoformat()}T12:00:00Z"></time>'
            f'<a href="/archive/wasde-{index:03d}.xls">xls</a></tr>'
        )
        release = _advance_month(release)
    refs = parse_wasde_index_pages(["<table>" + "".join(rows) + "</table>"])
    assert len(refs) == 190
    assert refs[0].release_date == date(2010, 7, 12)
    assert refs[-1].url.endswith("wasde-189.xls")
    with pytest.raises(ValueError, match="release depth"):
        parse_wasde_index_pages(["<table>" + "".join(rows[:-1]) + "</table>"])


def test_workbook_parser_uses_rightmost_projected_crop_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSheet:
        def __init__(self, title: str, section: str | None, use: float, stocks: float) -> None:
            self.name = title
            self.nrows = 8
            self.ncols = 5
            self.cells = [["" for _ in range(self.ncols)] for _ in range(self.nrows)]
            self.cells[0][0] = title
            self.cells[1][0] = section or ""
            self.cells[1][4] = "2026/27 Proj."
            self.cells[5][0] = "Use, Total"
            self.cells[5][3] = use - 10
            self.cells[5][4] = use
            self.cells[6][0] = "Ending Stocks"
            self.cells[6][3] = stocks - 5
            self.cells[6][4] = stocks

        def cell_value(self, row: int, column: int) -> object:
            return self.cells[row][column]

    class FakeWorkbook:
        @staticmethod
        def sheets() -> list[FakeSheet]:
            return [
                FakeSheet("U.S. Wheat Supply and Use", None, 200.0, 40.0),
                FakeSheet("U.S. Feed Grain and Corn Supply and Use", "CORN", 300.0, 30.0),
                FakeSheet(
                    "U.S. Soybeans and Products Supply and Use", "SOYBEANS", 250.0, 25.0
                ),
            ]

    monkeypatch.setattr(
        "auto_invest.analytics.usda_crop_supply_demand_factory.xlrd.open_workbook",
        lambda **_: FakeWorkbook(),
    )
    ref = WasdeWorkbookRef(date(2026, 8, 12), "https://esmis.nal.usda.gov/wasde.xls")
    parsed = parse_wasde_workbook(b"archived-wasde", ref=ref)
    assert set(parsed) == {"corn", "wheat", "soybeans"}
    assert parsed["corn"].market_year == "2026/27"
    assert parsed["corn"].stocks_to_use == pytest.approx(0.1)
    assert parsed["wheat"].stocks_to_use == pytest.approx(0.2)


def _release_observations(index: int, market_year: str) -> dict[str, WasdeCropObservation]:
    release_date = date(2010 + index // 12, index % 12 + 1, 12)
    output: dict[str, WasdeCropObservation] = {}
    for offset, crop in enumerate(("corn", "wheat", "soybeans")):
        ratio = 0.30 - index / 10_000 - offset / 100
        output[crop] = WasdeCropObservation(
            release_date,
            crop,
            market_year,
            ratio * 100,
            100.0,
            ratio,
            f"https://example.test/{index}.xls",
            f"sha256:{index}",
        )
    return output


def test_marketing_year_rollover_is_neutral_not_a_false_scarcity_signal() -> None:
    releases = [
        _release_observations(index, "2025/26" if index < 100 else "2026/27")
        for index in range(190)
    ]
    snapshots = build_revision_snapshots(releases)
    assert snapshots[99].revisions[1]["corn"] > 0
    assert snapshots[100].revisions[1]["corn"] == 0
    assert snapshots[102].revisions[3]["corn"] == 0
    assert snapshots[103].revisions[3]["corn"] > 0


def test_candidate_grammar_target_rule_and_actual_power_are_frozen() -> None:
    candidates = generate_crop_supply_demand_candidates()
    assert len(candidates) == 16
    assert len({item.candidate_id for item in candidates}) == 16
    assert len({item.strategy_fingerprint for item in candidates}) == 16
    assert {item.policy.family for item in candidates} == {
        "corn_tightening",
        "wheat_tightening",
        "soybean_tightening",
        "synchronized_tightening",
    }
    policy = CropSupplyDemandPolicy("synchronized_tightening", 3, Decimal("0.5"))
    assert crop_target_gold_weight(policy, {"corn": 1, "wheat": 1, "soybeans": 1}) == Decimal(
        "0.5"
    )
    assert crop_target_gold_weight(policy, {"corn": 1, "wheat": -1, "soybeans": 1}) == 0
    power = actual_holdout_psr_power(131)
    assert power["null_false_positive_approx"] == 0.05
    assert power["detection_by_true_annual_sharpe"]["1.0"] > 0.90


def test_factory_keeps_720_trials_and_untouched_holdout() -> None:
    first = _run()
    assert first["candidate_count"] == 16
    assert first["prior_trial_count"] == 704
    assert first["global_audit_trial_count"] == 720
    assert first["unique_trial_fingerprint_count"] == 720
    assert first["supply_demand_data_fingerprint"] == "sha256:prior-supply-demand-data"
    assert first["development_selection"]["months"] == 60
    assert first["holdout_confirmation"]["embargo_months"] == 1
    assert first["holdout_confirmation"]["months"] == 131
    assert first["decision"]["criterion_diagnosis"].startswith("PASSABLE")
    assert first["decision"]["research_canary_eligible"] is False
    assert first["research_live_parity"]["passed"] is False

    changed = deepcopy(_bundle())
    revisions = deepcopy(changed.revisions)
    for horizon in revisions:
        for crop, values in revisions[horizon].items():
            mutable = list(values)
            for index in range(62, len(mutable)):
                mutable[index] *= -1
            revisions[horizon][crop] = tuple(mutable)
    object.__setattr__(changed, "revisions", revisions)
    second = _run(changed)
    assert (
        first["development_selection"]["selected_candidate_id"]
        == second["development_selection"]["selected_candidate_id"]
    )


def test_controls_fail_closed_and_source_has_no_broker_boundary() -> None:
    failed = _run(controls=_controls(False))
    gates = {row["gate_id"]: row for row in failed["decision"]["gates"]}
    assert gates["full_gate_controls"]["passed"] is False
    assert failed["decision"]["criterion_diagnosis"] == "CRITERIA_OR_CONTROLS_INVALID"
    assert failed["decision"]["research_canary_eligible"] is False

    from pathlib import Path

    source = Path("src/auto_invest/analytics/usda_crop_supply_demand_factory.py").read_text()
    assert "auto_invest.brokers" not in source
    assert "KisBroker" not in source
