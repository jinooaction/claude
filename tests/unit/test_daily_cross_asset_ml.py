"""Spec 146 core model, chronology, and risk-boundary tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from auto_invest.analytics.daily_cross_asset_ml import (
    UNIVERSE,
    DailyClose,
    DailyMLEdgeDataError,
    build_panel,
    run_daily_cross_asset_ml,
)


def _sessions(count: int = 1300) -> list[str]:
    out: list[str] = []
    current = date(2019, 1, 7)
    while len(out) < count:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _predictable_daily() -> dict[str, list[DailyClose]]:
    sessions = _sessions()
    out: dict[str, list[DailyClose]] = {}
    for asset_index, symbol in enumerate(UNIVERSE):
        price = 100.0
        rows: list[DailyClose] = []
        for session_index, raw_date in enumerate(sessions):
            week = session_index // 5
            weekly_return = 0.02 if (week + asset_index) % 2 == 0 else -0.012
            price *= (1 + weekly_return) ** (1 / 5)
            rows.append(DailyClose(raw_date, price, 1_000_000))
        out[symbol] = rows
    return out


def test_predictable_mean_reversion_passes_strict_gates_without_leakage():
    daily = _predictable_daily()
    dates, _levels, _returns, panel = build_panel(daily)
    report = run_daily_cross_asset_ml(daily)

    assert dates == sorted(dates)
    assert all(row.target_index == row.feature_index + 1 for row in panel)
    assert all(fold.chronology_ok for fold in report.folds)
    assert all(fold.train_label_end < fold.test_start for fold in report.folds)
    assert report.verdict == "DAILY_ML_EDGE_CANDIDATE_READY"
    assert len(report.folds) >= 10
    assert report.candidate_package["eligible"] is True
    assert report.candidate_package["live_promotion_authorized"] is False


def test_latest_allocation_is_long_only_capped_and_keeps_explicit_cash():
    report = run_daily_cross_asset_ml(_predictable_daily())
    weights = report.latest_allocation["weights"]

    assert 0 < sum(value > 0 for value in weights.values()) <= 4
    assert all(0 <= value <= 0.25 for value in weights.values())
    assert sum(weights.values()) <= 0.99 + 1e-12
    assert report.latest_allocation["cash_weight"] == pytest.approx(
        1 - sum(weights.values())
    )


def test_incomplete_or_shallow_universe_fails_closed():
    daily = _predictable_daily()
    daily.pop("UUP")
    with pytest.raises(DailyMLEdgeDataError, match="universe mismatch"):
        build_panel(daily)

    shallow = _predictable_daily()
    shallow["UUP"] = shallow["UUP"][:100]
    with pytest.raises(DailyMLEdgeDataError, match="needs at least"):
        build_panel(shallow)
