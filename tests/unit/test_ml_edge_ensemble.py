"""Spec 145 machine-learning edge experiment contract tests."""

from __future__ import annotations

import math
from datetime import date

import pytest

from auto_invest.analytics.ml_edge_ensemble import (
    ASSETS,
    MLEdgeConfig,
    build_panel,
    constrained_weights,
    run_ml_edge_ensemble,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow


def _monthly_data(months: int = 180) -> tuple[list[MonthlyRow], list[float]]:
    rows: list[MonthlyRow] = []
    equity = 100.0
    gold = 80.0
    gold_levels: list[float] = []
    for index in range(months):
        year = 2000 + index // 12
        month = index % 12 + 1
        cycle = math.sin(index / 7.0)
        equity *= 1.0 + 0.006 + 0.012 * cycle
        gold *= 1.0 + 0.003 - 0.008 * cycle
        rows.append(
            MonthlyRow(
                date=date(year, month, 1).isoformat(),
                price=equity,
                dividend=2.0,
                long_rate=3.0 + cycle,
                earnings=5.0,
                cpi=100.0 * (1.002**index),
            )
        )
        gold_levels.append(gold)
    return rows, gold_levels


def _fast_config() -> MLEdgeConfig:
    return MLEdgeConfig(
        min_train_months=48,
        validation_months=12,
        test_months=12,
        purge_months=1,
        feature_lookback_months=12,
        boosting_estimators=8,
        boosting_min_samples_leaf=4,
    )


def _macro_signal_data(*, aligned: bool) -> tuple[list[MonthlyRow], list[float]]:
    months = 360
    rates = [2.0 if ((index * 37) % 101) < 50 else 7.0 for index in range(months)]
    equity = [100.0]
    gold = [100.0]
    for index in range(months - 1):
        signal_low = rates[index] < 4.0
        if not aligned:
            signal_low = ((index * 53 + 17) % 103) < 51
        equity.append(equity[-1] * (1.04 if signal_low else 0.99))
        gold.append(gold[-1] * (0.99 if signal_low else 1.04))
    rows = [
        MonthlyRow(
            date=date(1990 + index // 12, index % 12 + 1, 1).isoformat(),
            price=equity[index],
            dividend=0.0,
            long_rate=rates[index],
            earnings=5.0,
            cpi=100.0 * (1.002**index),
        )
        for index in range(months)
    ]
    return rows, gold


def test_panel_target_is_the_return_after_feature_month():
    rows, gold = _monthly_data()
    panel, returns, _, _ = build_panel(rows, gold, _fast_config())

    first = panel[0]
    assert first.target_index == first.feature_index + 1
    assert first.target_return == pytest.approx(returns[first.asset][first.feature_index])
    assert first.date == rows[first.feature_index].date
    assert first.target_date == rows[first.target_index].date


def test_constrained_weights_respect_asset_and_total_caps():
    weights = constrained_weights(
        {"equity": 100.0, "bond": 2.0, "gold": 1.0},
        total_weight=0.99,
        max_asset_weight=0.40,
    )

    assert set(weights) == set(ASSETS)
    assert max(weights.values()) <= 0.40
    assert sum(weights.values()) <= 0.99 + 1e-12
    assert all(value >= 0 for value in weights.values())


def test_walk_forward_is_purged_deterministic_and_no_live():
    rows, gold = _monthly_data()

    first = run_ml_edge_ensemble(rows, gold, _fast_config())
    second = run_ml_edge_ensemble(rows, gold, _fast_config())

    assert first.as_dict() == second.as_dict()
    assert all(fold.chronology_ok for fold in first.folds)
    assert all(fold.train_label_end < fold.test_start for fold in first.folds)
    assert first.safety == {
        "orders_submitted": 0,
        "orders_cancelled": 0,
        "live_strategy_changed": False,
        "capital_changed": False,
        "whitelist_changed": False,
        "caps_changed": False,
    }
    assert first.candidate_package["live_promotion_authorized"] is False


def test_predictable_signal_can_pass_but_unrelated_signal_cannot():
    config = MLEdgeConfig(
        min_train_months=60,
        validation_months=24,
        test_months=12,
        feature_lookback_months=12,
        boosting_estimators=12,
        boosting_min_samples_leaf=4,
    )
    aligned_rows, aligned_gold = _macro_signal_data(aligned=True)
    noise_rows, noise_gold = _macro_signal_data(aligned=False)

    ready = run_ml_edge_ensemble(aligned_rows, aligned_gold, config)
    rejected = run_ml_edge_ensemble(noise_rows, noise_gold, config)

    assert ready.verdict == "ML_EDGE_CANDIDATE_READY"
    assert ready.candidate_package["eligible"] is True
    assert rejected.verdict == "NO_EDGE"
    assert rejected.candidate_package["eligible"] is False
