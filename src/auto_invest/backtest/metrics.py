"""Backtest metrics (T021) — total return, max drawdown, Sharpe.

Implements R-B4: Sharpe is annualised by `sqrt(252)`, risk-free rate `0.0`,
geometric mean of daily returns. R-B11: pure numpy/pandas, no external
backtest-stats library, so the supply-chain surface stays tiny.

All inputs and outputs are `Decimal` (canonicalised to 6 dp via
`canonicalise_decimal`) so the FR-B15 byte-equality contract holds for
`metrics.csv` across machines and Python builds. Internal arithmetic is
done in `numpy.float64` for speed; the conversion back to Decimal happens
at the boundary.

Public API:

    total_return_pct(equity_curve)   -> Decimal
    max_drawdown_pct(equity_curve)   -> Decimal  (positive)
    sharpe_ratio(daily_returns)      -> Decimal  (annualised, RFR=0)
    aggregate_metrics(per_rule)      -> tuple[Decimal, Decimal, Decimal]

Equity curves are sequences of dollar values (or any positive monotone
unit) indexed by session date. `daily_returns` are simple period-over-
period returns (Pₜ / Pₜ₋₁ − 1).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

import numpy as np

from .data_model import RuleBacktestResult, canonicalise_decimal

TRADING_DAYS_PER_YEAR = 252


def _to_float_array(values: Iterable[Decimal | float | int]) -> np.ndarray:
    return np.asarray([float(v) for v in values], dtype=np.float64)


def total_return_pct(equity_curve: Sequence[Decimal | float | int]) -> Decimal:
    """Gross total return percentage (Pₙ / P₀ − 1) × 100.

    Returns a Decimal canonicalised to 6 dp. Empty or single-point curves
    return 0.000000 (no return is observable).
    """
    arr = _to_float_array(equity_curve)
    if arr.size < 2:
        return Decimal(canonicalise_decimal("0"))
    if arr[0] == 0:
        raise ValueError("equity_curve cannot start at 0")
    pct = (arr[-1] / arr[0] - 1.0) * 100.0
    return Decimal(canonicalise_decimal(pct))


def max_drawdown_pct(equity_curve: Sequence[Decimal | float | int]) -> Decimal:
    """Maximum peak-to-trough drawdown as a positive percentage.

    Computes ((peak − trough) / peak) × 100 over the worst trough that
    follows each running peak. Returns 0.000000 for monotonically
    non-decreasing curves.
    """
    arr = _to_float_array(equity_curve)
    if arr.size < 2:
        return Decimal(canonicalise_decimal("0"))
    if np.any(arr <= 0):
        raise ValueError("equity_curve must be strictly positive")
    running_max = np.maximum.accumulate(arr)
    drawdowns = (running_max - arr) / running_max
    dd = float(drawdowns.max() * 100.0)
    return Decimal(canonicalise_decimal(dd))


def sharpe_ratio(daily_returns: Sequence[Decimal | float | int]) -> Decimal:
    """Annualised Sharpe ratio per R-B4: mean / stdev × sqrt(252), RFR=0.

    Uses the sample standard deviation (ddof=1) so the convention matches
    pandas/numpy defaults. Returns 0.000000 when stdev is zero (constant
    return series — no risk, no excess to reward) or when fewer than two
    observations are provided.
    """
    arr = _to_float_array(daily_returns)
    if arr.size < 2:
        return Decimal(canonicalise_decimal("0"))
    std = float(np.std(arr, ddof=1))
    if std == 0.0:
        return Decimal(canonicalise_decimal("0"))
    mean = float(np.mean(arr))
    sharpe = (mean / std) * float(np.sqrt(TRADING_DAYS_PER_YEAR))
    return Decimal(canonicalise_decimal(sharpe))


def daily_returns_from_equity(
    equity_curve: Sequence[Decimal | float | int],
) -> list[Decimal]:
    """Convert an equity curve to per-period simple returns.

    Returns N-1 values for an N-point curve. Useful as the input to
    `sharpe_ratio` when the caller has an equity series, not returns.
    """
    arr = _to_float_array(equity_curve)
    if arr.size < 2:
        return []
    if np.any(arr[:-1] == 0):
        raise ValueError("equity_curve cannot contain zeros except possibly at the end")
    rets = arr[1:] / arr[:-1] - 1.0
    return [Decimal(canonicalise_decimal(r)) for r in rets.tolist()]


def aggregate_metrics(
    per_rule: Sequence[RuleBacktestResult],
) -> tuple[Decimal, Decimal, Decimal]:
    """Equal-weighted aggregate of per-rule (return, drawdown, Sharpe).

    v1 uses simple equal weighting (data-model.md § BacktestSummary). For an
    empty input, returns (0, 0, 0) canonicalised. The drawdown aggregate is
    a max (worst-of-rules) rather than a mean, because portfolio risk is
    bounded by the worst single rule's drawdown when rules are weighted
    equally.
    """
    if not per_rule:
        zero = Decimal(canonicalise_decimal("0"))
        return zero, zero, zero
    returns = np.array([float(r.total_return_pct) for r in per_rule], dtype=np.float64)
    drawdowns = np.array([float(r.max_drawdown_pct) for r in per_rule], dtype=np.float64)
    sharpes = np.array([float(r.sharpe_ratio) for r in per_rule], dtype=np.float64)
    return (
        Decimal(canonicalise_decimal(float(returns.mean()))),
        Decimal(canonicalise_decimal(float(drawdowns.max()))),
        Decimal(canonicalise_decimal(float(sharpes.mean()))),
    )


__all__ = [
    "TRADING_DAYS_PER_YEAR",
    "aggregate_metrics",
    "daily_returns_from_equity",
    "max_drawdown_pct",
    "sharpe_ratio",
    "total_return_pct",
]
