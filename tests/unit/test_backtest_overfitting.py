from decimal import Decimal

from auto_invest.analytics.backtest_overfitting import (
    deflated_sharpe_from_trials,
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
