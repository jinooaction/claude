from __future__ import annotations

import csv
import io
import math
from copy import deepcopy
from datetime import date

import pytest

from auto_invest.analytics.pead_factory import (
    EXPECTED_CANDIDATES,
    PeadBundle,
    PeadMonth,
    PeadPair,
    build_pead_bundle,
    generate_pead_candidates,
    parse_open_asset_pricing_csv,
    run_pead_factory,
)


def _months() -> list[PeadMonth]:
    rows: list[PeadMonth] = []
    year, month = 1971, 9
    index = 0
    while (year, month) <= (2024, 12):
        observed = date(year, month, 1)
        cycle = math.sin(index / 7.0) * 0.003
        rows.extend(
            [
                PeadMonth("AnnouncementReturn", observed, 0.012 + cycle, 300, 299),
                PeadMonth("EarningsSurprise", observed, 0.009 - cycle / 2, 280, 279),
            ]
        )
        index += 1
        month += 1
        if month == 13:
            year += 1
            month = 1
    return rows


def _bundle(rows: list[PeadMonth] | None = None) -> PeadBundle:
    return build_pead_bundle(
        rows or _months(),
        data_digest="sha256:" + "a" * 64,
        release="2025-10",
    )


def _prior_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for family in range(20):
        count = 16 if family < 10 else 64
        for index in range(count):
            rows.append(
                {
                    "candidate_id": f"prior-{family:02d}-{index:03d}",
                    "strategy_fingerprint": f"sha256:prior-{family:02d}-{index:03d}",
                    "status": "complete",
                    "batch_id": f"prior-family-{family:02d}",
                }
            )
    assert len(rows) == 800
    return rows


def _calibration() -> dict[str, object]:
    return {
        "code_commit": "abc123",
        "scenario": {"seed": 60_000, "repetitions": 500},
        "family_calibrations": {
            "16": {
                "null_research_entry_acceptance_rate": 0.01,
                "target_research_entry_detection_rate": 0.84,
            },
            "64": {
                "null_research_entry_acceptance_rate": 0.004,
                "target_research_entry_detection_rate": 0.804,
            },
        },
        "program_extension": {
            "gate_version": "3.2",
            "method": "family-size-bonferroni-v2",
            "family_caps": {"16": 0.01, "64": 0.009},
            "family_mix": {"16": 11, "64": 10},
            "conservative_upper_bound": 0.2,
            "false_acceptance_budget": 0.2,
            "planted_sharpe_annual": 0.6,
            "detection_min": 0.8,
            "minimum_repetitions": 500,
            "calibrated": True,
            "capital_entry_eligible": False,
        },
    }


def _preregistration() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "family_id": "equity-post-earnings-announcement-drift",
        "diagnostic_gate_version": "3.2",
        "data": {
            "provider": "Open Source Asset Pricing",
            "release": "2025-10",
            "url": "https://drive.google.com/uc?id=1g7w-yQ6Cg2qbMEkER9Q3vgns4JszXQo6",
            "signals": ["EarningsSurprise", "AnnouncementReturn"],
            "portfolio": "LS",
            "required_last_month": "2024-12",
            "expected_content_digest": "sha256:" + "a" * 64,
            "require_positive_long_short_counts": True,
        },
        "program_calibration": {
            "contract": "family-size-bonferroni-v2",
            "seed": 60_000,
            "minimum_repetitions": 500,
            "family_caps": {"16": 0.01, "64": 0.009},
            "family_mix": {"16": 11, "64": 10},
            "false_acceptance_budget": 0.2,
            "conservative_upper_bound": 0.2,
            "planted_sharpe_annual": 0.6,
            "detection_min": 0.8,
            "capital_entry_eligible": False,
        },
        "candidates": {
            "announcement_weights": [index / 7 for index in range(8)],
            "sleeve_scales": [0.5, 1.0],
            "expected_count": 16,
        },
        "split": {
            "development_end": "1996-12",
            "embargo_start": "1997-01",
            "embargo_end": "1997-12",
            "post_publication_start": "1998-01",
            "post_publication_end": "2015-12",
            "recent_start": "2016-01",
            "recent_required_months": 108,
        },
        "costs": {"primary_annual_bps": 150, "stress_annual_bps": [300, 500]},
        "gates": {
            "family_pbo_max": 0.25,
            "post_publication_psr_min": 0.95,
            "post_publication_annual_excess_min": 0.01,
            "positive_eras_required": 3,
            "era_count": 4,
            "positive_recent_windows_required": 2,
            "recent_window_count": 3,
            "positive_year_contribution_max": 0.25,
            "positive_top_five_month_contribution_max": 0.5,
            "maximum_drawdown_max": 0.3,
            "stress_300_annual_excess_min": 0.0,
            "sign_flip_must_fail": True,
        },
        "criterion_validity": {
            "feasibility_preview_contaminated": True,
            "untouched_holdout": False,
            "point_in_time_constituents": False,
            "account_execution_parity": False,
        },
        "forward_observation": {
            "start_date": "2026-09-01",
            "required_earnings_events": 200,
            "required_calendar_months": 12,
        },
        "safety": {
            "research_only": True,
            "research_canary_eligible": False,
            "promotion_allowed": False,
            "capital_allocation_fraction": 0.0,
            "orders_submitted": 0,
            "selected_deploy_config": None,
        },
    }


def _run(bundle: PeadBundle | None = None) -> dict[str, object]:
    return run_pead_factory(
        bundle=bundle or _bundle(),
        prior_audit_records=_prior_rows(),
        calibration=_calibration(),
        preregistration=_preregistration(),
        code_commit="abc123",
        generated_at="2026-08-31T00:00:00Z",
    )


def _csv_payload(rows: list[list[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["signalname", "port", "date", "ret", "signallag", "Nlong", "Nshort"])
    writer.writerows(rows)
    return buffer.getvalue().encode()


def test_parser_selects_two_ls_signals_and_validates_counts_and_dates() -> None:
    payload = _csv_payload(
        [
            ["AM", "LS", "2024-12-31", 99, "NA", 1, 1],
            ["AnnouncementReturn", "LS", "2024-11-29", 2.5, "NA", 12, 11],
            ["AnnouncementReturn", "LS", "2024-12-31", -1.5, "NA", 13, 12],
            ["EarningsSurprise", "LS", "2024-11-29", 1.0, "NA", 10, 9],
            ["EarningsSurprise", "LS", "2024-12-31", 0.5, "NA", 11, 10],
        ]
    )
    rows = parse_open_asset_pricing_csv(payload)
    assert len(rows) == 4
    assert rows[0] == PeadMonth("AnnouncementReturn", date(2024, 11, 1), 0.025, 12, 11)
    assert rows[-1].return_decimal == 0.005

    with pytest.raises(ValueError, match="positive long and short"):
        parse_open_asset_pricing_csv(
            _csv_payload(
                [
                    ["AnnouncementReturn", "LS", "2024-12-31", 1, "NA", 0, 1],
                    ["EarningsSurprise", "LS", "2024-12-31", 1, "NA", 1, 1],
                ]
            )
        )
    with pytest.raises(ValueError, match="duplicated"):
        parse_open_asset_pricing_csv(
            _csv_payload(
                [
                    ["AnnouncementReturn", "LS", "2024-12-31", 1, "NA", 1, 1],
                    ["AnnouncementReturn", "LS", "2024-12-31", 1, "NA", 1, 1],
                    ["EarningsSurprise", "LS", "2024-12-31", 1, "NA", 1, 1],
                ]
            )
        )


def test_bundle_requires_complete_common_months_and_exact_recent_window() -> None:
    bundle = _bundle()
    assert len(bundle.development) == 304
    assert len(bundle.embargo) == 12
    assert len(bundle.post_publication_pre_recent) == 216
    assert len(bundle.recent) == 108
    assert bundle.quality["latest_month"] == "2024-12"
    assert bundle.quality["all_long_short_counts_positive"] is True

    with_extra_surprise_history = [
        PeadMonth("EarningsSurprise", date(1971, 8, 1), 0.01, 10, 10),
        *_months(),
    ]
    accepted = _bundle(with_extra_surprise_history)
    assert accepted.quality["signal_start_months"] == {
        "AnnouncementReturn": "1971-09",
        "EarningsSurprise": "1971-08",
    }

    with pytest.raises(ValueError, match="common monthly history"):
        _bundle(_months()[:-1])


def test_generates_exactly_sixteen_preregistered_candidates() -> None:
    candidates = generate_pead_candidates()
    assert len(candidates) == EXPECTED_CANDIDATES == 16
    assert len({row.candidate_id for row in candidates}) == 16
    assert len({row.strategy_fingerprint for row in candidates}) == 16
    assert {row.policy.sleeve_scale for row in candidates} == {0.5, 1.0}
    assert {round(row.policy.announcement_weight, 12) for row in candidates} == {
        round(index / 7, 12) for index in range(8)
    }


def test_post_development_mutation_cannot_reselect_winner() -> None:
    baseline = _bundle()
    mutated = PeadBundle(
        development=baseline.development,
        embargo=baseline.embargo,
        post_publication_pre_recent=tuple(
            PeadPair(
                row.observed_month,
                -row.announcement_return * 5,
                -row.surprise_return * 5,
                row.announcement_long_count,
                row.announcement_short_count,
                row.surprise_long_count,
                row.surprise_short_count,
            )
            for row in baseline.post_publication_pre_recent
        ),
        recent=tuple(
            PeadPair(
                row.observed_month,
                row.announcement_return * 8,
                row.surprise_return * 8,
                row.announcement_long_count,
                row.announcement_short_count,
                row.surprise_long_count,
                row.surprise_short_count,
            )
            for row in baseline.recent
        ),
        quality=baseline.quality,
    )
    assert _run(baseline)["development_selection"] == _run(mutated)["development_selection"]
    assert _run(baseline)["historical_evaluation"] != _run(mutated)["historical_evaluation"]


def test_result_has_816_unique_rows_21_families_and_closed_money_path() -> None:
    result = _run()
    assert result["candidate_count"] == 16
    assert result["global_audit"] == {
        "trial_count": 816,
        "unique_candidate_id_count": 816,
        "unique_strategy_fingerprint_count": 816,
        "family_count": 21,
        "family_size_counts": {"16": 11, "64": 10},
    }
    assert result["program_calibration"]["conservative_upper_bound"] == 0.2
    assert result["verdict"] == "PUBLISHED_EDGE"
    assert result["decision"]["selected_candidate_id"] is not None
    assert result["decision"]["selected_deploy_config"] is None
    assert result["criterion_validity"] == _preregistration()["criterion_validity"]
    assert result["forward_observation"]["observed_earnings_events"] == 0
    assert result["forward_observation"]["observed_calendar_months"] == 0
    assert result["safety"] == {
        "research_only": True,
        "research_canary_eligible": False,
        "promotion_allowed": False,
        "capital_allocation_fraction": 0.0,
        "orders_submitted": 0,
        "selected_deploy_config": None,
    }


def test_calibration_prior_audit_and_safety_contract_fail_closed() -> None:
    with pytest.raises(ValueError, match="800"):
        run_pead_factory(
            bundle=_bundle(),
            prior_audit_records=_prior_rows()[:-1],
            calibration=_calibration(),
            preregistration=_preregistration(),
            code_commit="abc123",
            generated_at="2026-08-31T00:00:00Z",
        )
    bad_calibration = deepcopy(_calibration())
    bad_calibration["program_extension"]["family_mix"]["16"] = 12
    with pytest.raises(ValueError, match="program calibration"):
        run_pead_factory(
            bundle=_bundle(),
            prior_audit_records=_prior_rows(),
            calibration=bad_calibration,
            preregistration=_preregistration(),
            code_commit="abc123",
            generated_at="2026-08-31T00:00:00Z",
        )
    bad_preregistration = deepcopy(_preregistration())
    bad_preregistration["safety"]["orders_submitted"] = 1
    with pytest.raises(ValueError, match="safety"):
        run_pead_factory(
            bundle=_bundle(),
            prior_audit_records=_prior_rows(),
            calibration=_calibration(),
            preregistration=bad_preregistration,
            code_commit="abc123",
            generated_at="2026-08-31T00:00:00Z",
        )
    bad_gate = deepcopy(_preregistration())
    bad_gate["gates"]["family_pbo_max"] = 0.30
    with pytest.raises(ValueError, match="gate contract"):
        run_pead_factory(
            bundle=_bundle(),
            prior_audit_records=_prior_rows(),
            calibration=_calibration(),
            preregistration=bad_gate,
            code_commit="abc123",
            generated_at="2026-08-31T00:00:00Z",
        )


def test_all_preregistered_historical_gates_are_exposed() -> None:
    result = _run()
    gate_ids = {row["gate_id"] for row in result["decision"]["gates"]}
    assert {
        "program_calibration",
        "family_pbo",
        "post_publication_psr",
        "post_publication_annual_excess",
        "positive_eras",
        "recent_36m_wins",
        "single_year_concentration",
        "top_five_month_concentration",
        "maximum_drawdown",
        "stress_300bps_positive",
        "sign_flipped_placebo_fails_core",
    } <= gate_ids
    assert len(result["historical_evaluation"]["recent_36m_annual_excess"]) == 3
    assert result["decision"]["threshold_change_after_results"] is False
