from __future__ import annotations

import io
import math
import zipfile
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.analytics.energy_cross_market_factory import (
    EnergyCrossMarketBundle,
    EnergyCrossMarketPolicy,
    EnergyFeatureSnapshot,
    _development_winner_index,
    calibrate_standalone_family,
    energy_target_weight,
    expanding_ridge_predictions,
    generate_energy_cross_market_candidates,
    parse_eia_monthly_series,
    parse_french_oil_returns,
    run_energy_cross_market_factory,
    standalone_lane,
    validate_energy_cross_market_bundle,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow


def _months(count: int, *, year: int = 1998, month: int = 1) -> list[str]:
    output: list[str] = []
    for _ in range(count):
        output.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return output


def _prior() -> dict:
    return {
        "usda_crop_data_fingerprint": "sha256:prior-usda-data",
        "audit_records": [
            {
                "candidate_id": f"prior-{index:03d}",
                "strategy_fingerprint": f"sha256:prior-{index:03d}",
                "status": "complete",
            }
            for index in range(720)
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


def _controls(valid: bool = True) -> dict:
    return {
        "verdict": "FULL_GATE_CONTROLS_VALID" if valid else "FULL_GATE_CONTROLS_FAILED",
        "promotion_control_passed": valid,
        "code_commit": "abc123",
        "control_fingerprint": "sha256:full-controls",
        "positive_control": {"passed": valid, "psr": "0.962691"},
        "null_control": {"passed": False, "psr": "0.434559"},
    }


def _bundle(count: int = 322) -> EnergyCrossMarketBundle:
    months = _months(count)
    energy = tuple(
        1.0 + 0.012 * math.sin(index / 3) + 0.006 for index in range(count)
    )
    cash = tuple(1.002 for _ in months)
    features: dict[int, tuple[EnergyFeatureSnapshot, ...]] = {}
    for horizon in (6, 12):
        rows: list[EnergyFeatureSnapshot] = []
        for index, month in enumerate(months):
            source_index = max(0, index - 2)
            source_month = months[source_index]
            rows.append(
                EnergyFeatureSnapshot(
                    target_month=date.fromisoformat(month),
                    source_month=date.fromisoformat(source_month),
                    horizon_months=horizon,
                    wti_return=math.sin(index / 5),
                    gasoline_return=math.sin(index / 5 + 0.2),
                    heating_return=math.sin(index / 5 + 0.4),
                    natural_gas_return=math.sin(index / 5 + 0.6),
                    crack_margin=12.0 + math.cos(index / 7),
                    crack_zscore=math.cos(index / 7),
                )
            )
        features[horizon] = tuple(rows)
    return EnergyCrossMarketBundle(
        factor_months=tuple(months),
        energy_factors=energy,
        cash_factors=cash,
        features=features,
        quality={"complete": True, "factor_months": count},
    )


def _rows(count: int = 322) -> list[MonthlyRow]:
    months = _months(count + 1, year=1997, month=12)
    return [
        MonthlyRow(
            month,
            100.0 * math.exp(index * 0.006 + 0.12 * math.sin(index / 8)),
            2.0 + 0.2 * math.sin(index / 9),
            4.0 + 0.5 * math.cos(index / 10),
        )
        for index, month in enumerate(months)
    ]


def test_eia_parser_requires_exact_identity_unit_and_two_month_lag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSheet:
        name = "Data 1"
        nrows = 303

        def cell_value(self, row: int, column: int) -> object:
            if row == 1 and column == 1:
                return "RWTC"
            if row == 2 and column == 1:
                return "Cushing WTI (Dollars per Barrel)"
            if row >= 3:
                return float(row - 3) if column == 0 else 60.0 + (row - 3) / 10
            return "unused"

    class FakeBook:
        datemode = 0

        @staticmethod
        def sheet_by_name(name: str) -> FakeSheet:
            assert name == "Data 1"
            return FakeSheet()

    monkeypatch.setattr(
        "auto_invest.analytics.energy_cross_market_factory.xlrd.open_workbook",
        lambda **_: FakeBook(),
    )
    monkeypatch.setattr(
        "auto_invest.analytics.energy_cross_market_factory.xlrd.xldate_as_datetime",
        lambda serial, _datemode: datetime(
            1998 + int(serial) // 12,
            int(serial) % 12 + 1,
            1,
        ),
    )
    parsed = parse_eia_monthly_series(b"fixed", "RWTC")
    assert len(parsed) == 300
    assert parsed[0].series_id == "RWTC"
    assert parsed[0].period_month == date(1998, 1, 1)
    assert parsed[0].available_month == date(1998, 3, 1)
    with pytest.raises(ValueError, match="identity"):
        parse_eia_monthly_series(b"fixed", "RNGWHHD")


def test_french_parser_extracts_value_weighted_oil_and_rejects_missing() -> None:
    rows = ["header", "  Average Value Weighted Returns -- Monthly", ",Food ,Oil  ,Util "]
    rows.extend(
        f"{month.replace('-', '')[:6]},1.0,{2.0 + index / 100:.2f},3.0"
        for index, month in enumerate(_months(301))
    )
    rows.extend(["", "  Average Equal Weighted Returns -- Monthly", ",Food ,Oil  ,Util "])
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("49_Industry_Portfolios.csv", "\n".join(rows))
    parsed = parse_french_oil_returns(raw.getvalue())
    assert len(parsed) == 301
    assert parsed[0][0] == date(1998, 1, 1)
    assert parsed[0][1] == pytest.approx(1.02)

    missing = io.BytesIO()
    with zipfile.ZipFile(missing, "w") as archive:
        archive.writestr("wrong.csv", "no monthly oil table")
    with pytest.raises(ValueError, match="Oil"):
        parse_french_oil_returns(missing.getvalue())


def test_candidate_grammar_and_rule_weights_are_frozen() -> None:
    candidates = generate_energy_cross_market_candidates()
    assert len(candidates) == 16
    assert len({item.candidate_id for item in candidates}) == 16
    assert len({item.strategy_fingerprint for item in candidates}) == 16
    assert {item.policy.family for item in candidates} == {
        "wti_trend",
        "refining_margin",
        "market_breadth",
        "ridge_forecast",
    }
    feature = _bundle().features[6][10]
    maximum = Decimal("0.5")
    assert energy_target_weight(EnergyCrossMarketPolicy("wti_trend", 6, maximum), feature) in {
        Decimal("0"),
        maximum,
    }
    assert energy_target_weight(
        EnergyCrossMarketPolicy("ridge_forecast", 6, maximum),
        feature,
        ridge_prediction=0.01,
    ) == maximum


def test_incomplete_or_stale_bundle_fails_before_publication() -> None:
    bundle = _bundle()
    object.__setattr__(bundle, "quality", {"complete": False})
    with pytest.raises(ValueError, match="incomplete or stale"):
        validate_energy_cross_market_bundle(bundle)


def test_development_ties_choose_lower_drawdown_then_stable_identity() -> None:
    records = [
        {
            "candidate_id": "candidate-b",
            "development_sharpe_excess_25bps": 0.5,
            "development_max_drawdown_25bps": 10.0,
        },
        {
            "candidate_id": "candidate-a",
            "development_sharpe_excess_25bps": 0.5,
            "development_max_drawdown_25bps": 10.0,
        },
        {
            "candidate_id": "candidate-c",
            "development_sharpe_excess_25bps": 0.5,
            "development_max_drawdown_25bps": 11.0,
        },
    ]
    assert _development_winner_index(records) == 1


def test_expanding_ridge_is_deterministic_and_never_uses_current_label() -> None:
    features = [
        (math.sin(index / 5), math.cos(index / 7), index / 100, 1.0, -0.5)
        for index in range(100)
    ]
    targets = [row[0] * 0.01 for row in features]
    first, chronology = expanding_ridge_predictions(features, targets, min_train=60)
    changed = list(targets)
    changed[80] = 100.0
    second, _ = expanding_ridge_predictions(features, changed, min_train=60)
    assert first == expanding_ridge_predictions(features, targets, min_train=60)[0]
    assert chronology[60]["latest_training_target_index"] == 59
    assert first[80] == second[80]
    assert first[81] != second[81]


def test_standalone_lane_is_not_the_legacy_diversifier_lane() -> None:
    cash = [1.001] * 240
    passive = [1.0 + 0.006 + 0.06 * math.sin(index) for index in range(240)]
    candidate = [1.0 + 0.008 + 0.02 * math.sin(index) for index in range(240)]
    lane = standalone_lane(candidate, cash, passive, active_fraction=0.5, paper=False)
    assert lane["gates"]["annual_cash_excess_50bps"]["passed"] is True
    assert lane["gates"]["energy_exposure_diversity"]["passed"] is True
    assert "incumbent_correlation" not in lane["gates"]


def test_family_calibration_is_passable_and_rejects_nulls() -> None:
    report = calibrate_standalone_family(201, repetitions=200, seed=16300)
    assert report["null_false_acceptance_rate"] <= 0.05
    assert report["planted_edge_detection_rate"] >= 0.70


def test_factory_preserves_736_trials_and_untouched_selection() -> None:
    first = run_energy_cross_market_factory(
        _rows(),
        [400.0 * math.exp(index * 0.004 + 0.08 * math.sin(index / 7)) for index in range(323)],
        _bundle(),
        prior_factory_payload=_prior(),
        calibration_evidence=_calibration(),
        full_gate_controls=_controls(),
        code_commit="abc123",
        timestamp_utc="2026-08-25T00:00:00Z",
        calibration_repetitions=100,
    )
    assert first["candidate_count"] == 16
    assert first["prior_trial_count"] == 720
    assert first["global_audit_trial_count"] == 736
    assert first["unique_trial_fingerprint_count"] == 736
    assert first["development_selection"]["months"] == 120
    assert first["holdout_confirmation"]["embargo_months"] == 1
    assert first["holdout_confirmation"]["months"] == 201
    assert first["selection_sanity"]["promotion_allowed"] is False
    assert first["decision"]["research_canary_eligible"] is False
    assert first["research_live_parity"]["passed"] is False

    changed = deepcopy(_bundle())
    factors = list(changed.energy_factors)
    for index in range(121, len(factors)):
        factors[index] = 2.0 - factors[index]
    object.__setattr__(changed, "energy_factors", tuple(factors))
    second = run_energy_cross_market_factory(
        _rows(),
        [400.0 * math.exp(index * 0.004 + 0.08 * math.sin(index / 7)) for index in range(323)],
        changed,
        prior_factory_payload=_prior(),
        calibration_evidence=_calibration(),
        full_gate_controls=_controls(),
        code_commit="abc123",
        timestamp_utc="2026-08-25T00:00:00Z",
        calibration_repetitions=100,
    )
    assert first["development_selection"]["selected_candidate_id"] == second[
        "development_selection"
    ]["selected_candidate_id"]


def test_controls_and_live_parity_fail_closed() -> None:
    report = run_energy_cross_market_factory(
        _rows(),
        [400.0 * (1.004**index) for index in range(323)],
        _bundle(),
        prior_factory_payload=_prior(),
        calibration_evidence=_calibration(),
        full_gate_controls=_controls(False),
        code_commit="abc123",
        timestamp_utc="2026-08-25T00:00:00Z",
        calibration_repetitions=50,
    )
    assert report["decision"]["criterion_diagnosis"] == "OBJECTIVE_OR_CONTROLS_INVALID"
    assert report["decision"]["research_canary_eligible"] is False
    assert report["research_live_parity"]["intended_symbol"] == "XLE"

    source = Path("src/auto_invest/analytics/energy_cross_market_factory.py").read_text(
        encoding="utf-8"
    )
    assert "auto_invest.broker" not in source
    assert "KisBroker" not in source
