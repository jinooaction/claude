from decimal import Decimal

from auto_invest.analytics.backtest_overfitting import (
    deflated_sharpe_from_trials,
    effective_independent_trials,
    probability_of_backtest_overfitting,
)


def test_pbo_is_low_for_consistent_winner() -> None:
    scores = [[2.0] * 10, [1.0] * 10, [0.0] * 10]
    assert probability_of_backtest_overfitting(scores) == Decimal("0.000000")


def test_pbo_is_high_for_rotating_in_sample_winners() -> None:
    scores = [
        [3, 3, 3, 3, 3, -3, -3, -3, -3, -3],
        [-3, -3, -3, -3, -3, 3, 3, 3, 3, 3],
        [0.2] * 10,
    ]
    pbo = probability_of_backtest_overfitting(scores)
    assert pbo is not None and pbo >= Decimal("0.500000")


def test_pbo_requires_even_segment_matrix() -> None:
    assert probability_of_backtest_overfitting([[1, 2, 3], [3, 2, 1]]) is None


def test_dsr_penalizes_wide_trial_search() -> None:
    returns = [0.01, 0.02, -0.01, 0.015] * 30
    narrow = deflated_sharpe_from_trials(returns, [0.2, 0.3])
    wide = deflated_sharpe_from_trials(returns, [-1, -0.5, 0, 0.5, 1, 1.5, 2])
    assert narrow is not None and wide is not None and wide < narrow


def test_effective_trials_discount_correlated_family_without_erasing_search() -> None:
    base = [float(index) / 100 for index in range(24)]
    correlated = [[value + trial / 10_000 for value in base] for trial in range(8)]
    effective = effective_independent_trials(correlated)
    assert Decimal("1") <= effective < Decimal("2")


def test_effective_trials_keep_raw_count_for_negative_or_invalid_dependence() -> None:
    alternating = [[(-1) ** (index + trial) for index in range(24)] for trial in range(4)]
    assert effective_independent_trials(alternating) == Decimal("4.000000")
    assert effective_independent_trials([[1.0] * 24, [2.0] * 24]) == Decimal("2.000000")


def test_dsr_accepts_bounded_effective_trial_count() -> None:
    returns = [0.01, 0.02, -0.01, 0.015] * 30
    raw = deflated_sharpe_from_trials(returns, [-1, -0.5, 0, 0.5, 1, 1.5, 2])
    effective = deflated_sharpe_from_trials(
        returns,
        [-1, -0.5, 0, 0.5, 1, 1.5, 2],
        effective_trial_count=Decimal("2.5"),
    )
    assert raw is not None and effective is not None and effective > raw
