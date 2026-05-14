"""T022 — backtest metrics tests.

Hand-computed reference values for total_return, max_drawdown, and Sharpe
to 6 dp (FR-B15 byte-stability), plus aggregate weighting checks.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from auto_invest.backtest.data_model import RuleBacktestResult, canonicalise_decimal
from auto_invest.backtest.metrics import (
    TRADING_DAYS_PER_YEAR,
    aggregate_metrics,
    daily_returns_from_equity,
    max_drawdown_pct,
    sharpe_ratio,
    total_return_pct,
)

# ---------- total_return_pct ---------------------------------------------


def test_total_return_monotone_increasing() -> None:
    curve = [100.0, 105.0, 110.0, 121.0]
    # 121 / 100 - 1 = 0.21 → 21.000000%
    assert total_return_pct(curve) == Decimal("21.000000")


def test_total_return_zero_for_flat_curve() -> None:
    assert total_return_pct([100.0, 100.0, 100.0]) == Decimal("0.000000")


def test_total_return_negative_for_loss() -> None:
    assert total_return_pct([100.0, 50.0]) == Decimal("-50.000000")


def test_total_return_empty_or_single_is_zero() -> None:
    assert total_return_pct([]) == Decimal("0.000000")
    assert total_return_pct([100.0]) == Decimal("0.000000")


def test_total_return_zero_start_raises() -> None:
    with pytest.raises(ValueError, match="cannot start at 0"):
        total_return_pct([0.0, 100.0])


# ---------- max_drawdown_pct ---------------------------------------------


def test_max_drawdown_monotone_curve_is_zero() -> None:
    assert max_drawdown_pct([100.0, 105.0, 110.0]) == Decimal("0.000000")


def test_max_drawdown_known_series() -> None:
    # Peak 100 -> trough 60 -> rebound 80. Drawdown = (100-60)/100 = 40%.
    curve = [100.0, 80.0, 60.0, 80.0]
    assert max_drawdown_pct(curve) == Decimal("40.000000")


def test_max_drawdown_only_counts_worst_after_each_peak() -> None:
    # Series: dip (50% from start), recover to new high, smaller dip.
    # First dip: peak=100 trough=50 -> 50%. After new peak=200 trough=180 -> 10%.
    # Max should still be 50%.
    curve = [100.0, 50.0, 200.0, 180.0]
    assert max_drawdown_pct(curve) == Decimal("50.000000")


def test_max_drawdown_empty_or_single_is_zero() -> None:
    assert max_drawdown_pct([]) == Decimal("0.000000")
    assert max_drawdown_pct([100.0]) == Decimal("0.000000")


def test_max_drawdown_negative_curve_raises() -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        max_drawdown_pct([100.0, -50.0, 80.0])


# ---------- sharpe_ratio --------------------------------------------------


def test_sharpe_constant_returns_zero() -> None:
    """No volatility → no excess to reward → Sharpe = 0 by convention."""
    assert sharpe_ratio([0.001, 0.001, 0.001, 0.001]) == Decimal("0.000000")


def test_sharpe_empty_or_single_is_zero() -> None:
    assert sharpe_ratio([]) == Decimal("0.000000")
    assert sharpe_ratio([0.01]) == Decimal("0.000000")


def test_sharpe_known_series_matches_hand_computation() -> None:
    """Hand-compute: returns r=[0.01, -0.005, 0.02, 0.0, 0.005].

    mean = 0.006, sample std (ddof=1) ≈ 0.00963067...
    Sharpe = 0.006 / 0.00963067 * sqrt(252)
           ≈ 0.622984... * 15.87450... ≈ 9.889754...
    """
    rets = [0.01, -0.005, 0.02, 0.0, 0.005]
    arr = np.array(rets)
    expected = (arr.mean() / arr.std(ddof=1)) * np.sqrt(TRADING_DAYS_PER_YEAR)
    expected_canonical = Decimal(canonicalise_decimal(float(expected)))
    assert sharpe_ratio(rets) == expected_canonical


def test_sharpe_positive_for_positive_drift() -> None:
    rng = np.random.default_rng(42)
    rets = (rng.normal(loc=0.001, scale=0.01, size=252)).tolist()
    s = sharpe_ratio(rets)
    assert s > 0


def test_sharpe_negative_for_negative_drift() -> None:
    rng = np.random.default_rng(7)
    rets = (rng.normal(loc=-0.002, scale=0.01, size=252)).tolist()
    s = sharpe_ratio(rets)
    assert s < 0


# ---------- daily_returns_from_equity ------------------------------------


def test_daily_returns_correct_arithmetic() -> None:
    curve = [100.0, 110.0, 99.0]
    # r1 = 110/100 - 1 = 0.10; r2 = 99/110 - 1 ≈ -0.10
    rets = daily_returns_from_equity(curve)
    assert rets[0] == Decimal("0.100000")
    assert rets[1] == Decimal(canonicalise_decimal(99.0 / 110.0 - 1.0))


def test_daily_returns_short_curve_returns_empty() -> None:
    assert daily_returns_from_equity([]) == []
    assert daily_returns_from_equity([100.0]) == []


# ---------- aggregate_metrics --------------------------------------------


def _result(*, return_pct: str, dd_pct: str, sharpe: str) -> RuleBacktestResult:
    return RuleBacktestResult(
        rule_id="r",
        symbol="AAPL",
        total_return_pct=Decimal(return_pct),
        max_drawdown_pct=Decimal(dd_pct),
        sharpe_ratio=Decimal(sharpe),
        order_count=0,
        fill_count=0,
        notional_traded_usd=Decimal("0"),
    )


def test_aggregate_empty_is_zero() -> None:
    ret, dd, s = aggregate_metrics([])
    assert ret == Decimal("0.000000")
    assert dd == Decimal("0.000000")
    assert s == Decimal("0.000000")


def test_aggregate_equal_weight_mean() -> None:
    rs = [
        _result(return_pct="10.000000", dd_pct="5.000000", sharpe="1.000000"),
        _result(return_pct="20.000000", dd_pct="15.000000", sharpe="2.000000"),
    ]
    ret, dd, s = aggregate_metrics(rs)
    assert ret == Decimal("15.000000")        # mean of 10, 20
    assert dd == Decimal("15.000000")         # max of 5, 15
    assert s == Decimal("1.500000")           # mean of 1, 2


def test_aggregate_drawdown_uses_worst_rule() -> None:
    """Aggregate drawdown is max(per_rule_dd), not mean."""
    rs = [
        _result(return_pct="0", dd_pct="2.000000", sharpe="0"),
        _result(return_pct="0", dd_pct="50.000000", sharpe="0"),
        _result(return_pct="0", dd_pct="5.000000", sharpe="0"),
    ]
    _, dd, _ = aggregate_metrics(rs)
    assert dd == Decimal("50.000000")


# ---------- byte-stability invariants ------------------------------------


def test_metrics_are_canonical_six_dp() -> None:
    """Every metric output must be a 6-dp canonical Decimal string."""
    out = total_return_pct([100.0, 137.0])
    assert str(out).count(".") == 1
    assert len(str(out).split(".")[1]) == 6

    out = max_drawdown_pct([100.0, 70.0, 90.0])
    assert len(str(out).split(".")[1]) == 6

    out = sharpe_ratio([0.01, 0.02, -0.01, 0.005])
    assert len(str(out).split(".")[1]) == 6
