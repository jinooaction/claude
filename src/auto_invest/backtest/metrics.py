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
from dataclasses import dataclass
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


def sortino_ratio(daily_returns: Sequence[Decimal | float | int]) -> Decimal:
    """Annualised Sortino ratio: mean / downside_deviation × sqrt(252), MAR=RFR=0.

    Sortino is Sharpe's downside-only sibling — it penalises only returns
    below the minimum acceptable return (MAR=0), so upside volatility is not
    treated as risk. Downside deviation is the target semideviation about a
    MAR of 0: sqrt(mean(min(0, r)²)) taken over ALL observations (the standard
    convention; the count is the full sample, not just the negative tail).

    Returns 0.000000 when fewer than two observations are provided or when
    there is no downside risk (downside deviation 0 — no negative return to
    penalise), mirroring sharpe_ratio's zero-risk path. Annualisation matches
    sharpe_ratio (sqrt(252)) so the two ratios are read on the same time base.
    """
    arr = _to_float_array(daily_returns)
    if arr.size < 2:
        return Decimal(canonicalise_decimal("0"))
    downside = np.minimum(arr, 0.0)
    dd = float(np.sqrt(np.mean(downside**2)))
    if dd == 0.0:
        return Decimal(canonicalise_decimal("0"))
    mean = float(np.mean(arr))
    sortino = (mean / dd) * float(np.sqrt(TRADING_DAYS_PER_YEAR))
    return Decimal(canonicalise_decimal(sortino))


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


# ----------------------------------------- trade-level metrics (single yardstick)
#
# 헌법 X.2 단일 잣대: 승률·손익비·실현거래 재구성은 라이브 성과 엔진(spec 011)과
# 백테스트(spec 016)가 같은 정의를 써야 한다. 그 정의를 여기 한 곳에 둔다 — 두
# 잣대가 갈라지지 못하게.


@dataclass(frozen=True)
class TradeFill:
    """Normalised fill — the single input shape for trade-level metrics shared
    by the live engine and the backtest. Callers adapt their own fill rows to
    this so the avg-cost reconstruction below cannot drift between yardsticks."""

    symbol: str
    side: str  # "BUY" | "SELL"
    qty: int
    price_usd: Decimal
    date: str = ""  # YYYY-MM-DD; lets callers bucket a realised-pnl equity curve
    rule_id: str | None = None


@dataclass(frozen=True)
class ClosedTrade:
    """One realised (closed) lot from a SELL, marked against running avg cost."""

    symbol: str
    qty: int
    pnl_usd: Decimal
    date: str
    rule_id: str | None


def realized_closed_trades(fills: Iterable[TradeFill]) -> list[ClosedTrade]:
    """Reconstruct realised closed trades from a fill sequence (average cost).

    THE single definition shared by live performance (spec 011) and the
    backtest (spec 016 slice 2). A SELL realises (fill_price − avg_cost) × qty
    against the running average cost; an oversell is clamped to the held qty
    (no synthetic short position), matching the live engine's data-quality rule.
    """
    avg_cost: dict[str, Decimal] = {}
    held: dict[str, int] = {}
    trades: list[ClosedTrade] = []
    for f in fills:
        q = held.get(f.symbol, 0)
        cost = avg_cost.get(f.symbol, Decimal("0"))
        if f.side == "BUY":
            new_q = q + f.qty
            new_total = cost * Decimal(q) + f.price_usd * Decimal(f.qty)
            avg_cost[f.symbol] = new_total / Decimal(new_q) if new_q else Decimal("0")
            held[f.symbol] = new_q
        elif f.side == "SELL":
            sell_qty = min(f.qty, q)
            if sell_qty <= 0:
                continue
            pnl = (f.price_usd - cost) * Decimal(sell_qty)
            trades.append(ClosedTrade(f.symbol, sell_qty, pnl, f.date, f.rule_id))
            held[f.symbol] = q - sell_qty
    return trades


@dataclass(frozen=True)
class WinLossStats:
    """Trade-level win/loss aggregation — the shared definition (헌법 X.2)."""

    closed_trades: int
    win_rate: Decimal | None  # 0..1 (winning closes / closes)
    avg_win_usd: Decimal | None
    avg_loss_usd: Decimal | None  # negative
    profit_factor: Decimal | None  # gross win / |gross loss|


def win_loss_stats(pnls: Sequence[Decimal]) -> WinLossStats:
    """Win rate, average win/loss, and profit factor from realised-trade pnls.

    Empty input → closed_trades 0 and every ratio None. profit_factor is None
    when there is no losing trade (no denominator). Pure Decimal arithmetic —
    these are operator-facing yardsticks, so the caller decides canonicalisation.
    """
    closed = len(pnls)
    if closed == 0:
        return WinLossStats(0, None, None, None, None)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = Decimal(len(wins)) / Decimal(closed)
    avg_win = (sum(wins, Decimal("0")) / Decimal(len(wins))) if wins else None
    avg_loss = (sum(losses, Decimal("0")) / Decimal(len(losses))) if losses else None
    gross_loss = abs(sum(losses, Decimal("0")))
    profit_factor = (sum(wins, Decimal("0")) / gross_loss) if gross_loss > 0 else None
    return WinLossStats(closed, win_rate, avg_win, avg_loss, profit_factor)


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
    "ClosedTrade",
    "TradeFill",
    "WinLossStats",
    "aggregate_metrics",
    "daily_returns_from_equity",
    "max_drawdown_pct",
    "realized_closed_trades",
    "sharpe_ratio",
    "sortino_ratio",
    "total_return_pct",
    "win_loss_stats",
]
