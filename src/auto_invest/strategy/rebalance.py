"""Cross-sectional portfolio rebalancing planner (spec 032).

NON-KERNEL. Pure, deterministic Decimal. This module turns the dormant alpha
toolkit (`strategy/factors.composite_scores` + `strategy/sizing` optimizers)
into an actual *portfolio*: it scores a universe, builds a target-weight vector
over the top-N names, and diffs that target against the current holdings to
produce the BUY **and SELL** orders that rebalance toward the target.

The SELL side is the dimension the rule-based system never had — when a name
falls out of the top ranks, ``rebalance_plan`` emits a full-exit SELL for it,
so losers are cut and winners are trimmed back to target weight instead of the
portfolio drifting forever (the single biggest realized-return leak in a
buy-only system).

Two stages:

  1. ``target_weights`` — selection (top_n / top_pct over the data-complete
     names, sentinel ``-Inf`` excluded) + weighting (``weight_scheme``). The
     risk-model schemes reuse the spec 022/024 optimizers verbatim, with the
     same fail-safe fallback chain (optimizer -> inverse-vol -> equal), so this
     module adds no new portfolio math — only the orchestration.
  2. ``rebalance_plan`` — target-dollar -> target-qty -> diff vs holdings ->
     ``PlannedOrder`` list, with a no-trade band (``rebalance_threshold_pct``)
     and a minimum-notional floor (``min_notional_usd``) for turnover control.

The planner only ever *proposes* quantities. Every BUY it produces is routed
through the unchanged K1 gate chain (`risk/gates.py`) by the caller (backtest /
later the live worker), so the per-trade / per-symbol / global caps remain the
true ceiling — the planner can never lift exposure above the safety boundary.
Long-only: weights are non-negative and sum to 1 (constitution domain — no
shorting in v1).

Deterministic Decimal (6 dp) so identical bars produce identical orders and
live == backtest (constitution X.2 single yardstick).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from auto_invest.strategy.sizing import (
    erc_group_scales,
    inverse_vol_group_scale,
    max_sharpe_group_scales,
    min_variance_group_scales,
    realized_volatility,
)
from auto_invest.strategy.trend import (
    TrendEnsembleSpec,
    TrendSpec,
    apply_trend_ensemble_filter,
    apply_trend_filter,
)

_QUANT = Decimal("0.000001")
_SENTINEL = Decimal("-Inf")
_ONE = Decimal("1")


def _canon(value: Decimal) -> Decimal:
    return value.quantize(_QUANT)


@dataclass(frozen=True)
class PlannedOrder:
    """One rebalancing order. ``side`` is "BUY" or "SELL"; ``qty`` is positive."""

    symbol: str
    side: str
    qty: int


# ----------------------------------------------------------------- selection


def select_symbols(
    ranked_scores: Sequence[tuple[str, Decimal]],
    *,
    top_n: int | None = None,
    top_pct: float | None = None,
) -> list[str]:
    """Top names from a descending composite ranking, sentinel-excluded.

    ``ranked_scores`` is the output of ``factors.composite_scores`` (already
    sorted best-first). Data-poor symbols carry the ``Decimal("-Inf")`` sentinel
    and are dropped before the cutoff so a data-rich name is never displaced by
    a data-poor one (same convention as the spec 021/023/025 filters). Exactly
    one of ``top_n`` / ``top_pct`` must be set.
    """
    eligible = [s for s, score in ranked_scores if score != _SENTINEL]
    if not eligible:
        return []
    if (top_n is None) == (top_pct is None):
        raise ValueError("select_symbols: set exactly one of top_n or top_pct")
    if top_n is not None:
        cutoff = min(top_n, len(eligible))
    else:
        cutoff = max(1, math.ceil(len(eligible) * (top_pct or 0) / 100))
    return eligible[:cutoff]


# ----------------------------------------------------------------- weighting


def _fix_residual(weights: dict[str, Decimal]) -> dict[str, Decimal]:
    """Absorb the 6-dp rounding residual into the largest weight so the vector
    sums to exactly ``Decimal("1.000000")`` (deterministic, tie-break by symbol).
    """
    if not weights:
        return weights
    total = sum(weights.values(), Decimal(0))
    residual = _canon(_ONE - total)
    if residual == 0:
        return weights
    target = max(weights, key=lambda k: (weights[k], k))
    adjusted = dict(weights)
    adjusted[target] = _canon(adjusted[target] + residual)
    return adjusted


def _normalize(raw: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Normalize a non-negative raw-weight map to sum exactly 1.0.

    A non-positive total (e.g. every raw weight 0) degrades to equal weights —
    a fail-safe so the planner always returns a valid long-only vector.
    """
    if not raw:
        return {}
    total = sum(raw.values(), Decimal(0))
    if total <= 0:
        eq = _canon(_ONE / Decimal(len(raw)))
        return _fix_residual({k: eq for k in raw})
    return _fix_residual({k: _canon(v / total) for k, v in raw.items()})


def _equal_weights(symbols: Sequence[str]) -> dict[str, Decimal]:
    return _normalize({s: _ONE for s in symbols})


def _score_proportional_weights(
    symbols: Sequence[str], score_by_symbol: Mapping[str, Decimal]
) -> dict[str, Decimal]:
    """Weight ∝ relative composite score (shifted so the minimum maps to 1).

    Shifting by ``1 - min_score`` keeps every weight strictly positive and
    monotone increasing in score, so a higher-scoring name always gets a larger
    weight (SC-02) without any name being assigned zero.
    """
    scores = [score_by_symbol[s] for s in symbols]
    min_score = min(scores)
    raw = {s: (score_by_symbol[s] - min_score + _ONE) for s in symbols}
    return _normalize(raw)


def _vols_by_symbol(
    symbols: Sequence[str],
    closes_by_symbol: Mapping[str, Mapping[date, Decimal]],
    lookback_bars: int,
) -> dict[str, Decimal | None]:
    vols: dict[str, Decimal | None] = {}
    for s in symbols:
        series = closes_by_symbol.get(s, {})
        ordered = [series[d] for d in sorted(series)]
        window = ordered[-(lookback_bars + 1) :]
        vols[s] = realized_volatility(window)
    return vols


def _inverse_vol_weights(
    symbols: Sequence[str], vols: Mapping[str, Decimal | None]
) -> dict[str, Decimal]:
    """Risk-parity: weight ∝ 1/vol (lowest-vol name keeps full size, others
    shrink). Reuses ``inverse_vol_group_scale`` so the math matches sizing."""
    all_vols = list(vols.values())
    raw = {s: inverse_vol_group_scale(vols.get(s), all_vols) for s in symbols}
    return _normalize(raw)


def target_weights(
    *,
    ranked_scores: Sequence[tuple[str, Decimal]],
    closes_by_symbol: Mapping[str, Mapping[date, Decimal]],
    weight_scheme: str = "equal",
    top_n: int | None = None,
    top_pct: float | None = None,
    lookback_bars: int = 60,
    trend: TrendSpec | TrendEnsembleSpec | None = None,
) -> dict[str, Decimal]:
    """Long-only target weights over the selected top names.

    ``ranked_scores`` come from ``factors.composite_scores``. The risk-model
    schemes (inverse_vol / min_variance / max_sharpe / erc) reuse the spec
    022/024 optimizers and their fail-safe fallback chains, so a data-poor or
    non-converging window still yields a valid vector (SC-04). Returns an empty
    dict when no symbol is eligible.

    When ``trend`` is given it is applied LAST, as a drawdown-defense overlay:
    * ``TrendSpec`` (spec 036, binary) — a selected name below its own trend is
      dropped to weight 0 (its share becomes cash).
    * ``TrendEnsembleSpec`` (spec 048, fractional) — a selected name is scaled by
      the *fraction of trend speeds it is above* (0, 1/N, …, 1); the rest is cash.
      The multi-speed consensus smooths the single-speed 0↔1 cliff (Sharpe ↑,
      drawdown ↓ in backtest).
    The result then sums to ≤ 1.0; it is intentionally NOT renormalized (the cash
    is the defense). With ``trend=None`` the behaviour is byte-identical (sum 1).
    """
    selected = select_symbols(ranked_scores, top_n=top_n, top_pct=top_pct)
    if not selected:
        return {}
    score_by_symbol = dict(ranked_scores)

    weights = _base_weights(
        selected, score_by_symbol, closes_by_symbol, weight_scheme, lookback_bars
    )
    if isinstance(trend, TrendEnsembleSpec):
        weights, _ = apply_trend_ensemble_filter(weights, closes_by_symbol, trend)
    elif trend is not None:
        weights, _ = apply_trend_filter(weights, closes_by_symbol, trend)
    return weights


def _base_weights(
    selected: list[str],
    score_by_symbol: dict[str, Decimal],
    closes_by_symbol: Mapping[str, Mapping[date, Decimal]],
    weight_scheme: str,
    lookback_bars: int,
) -> dict[str, Decimal]:
    """Weight vector (sum 1.0) for the selected names by ``weight_scheme``."""
    if weight_scheme == "equal":
        return _equal_weights(selected)
    if weight_scheme == "score_proportional":
        return _score_proportional_weights(selected, score_by_symbol)

    vols = _vols_by_symbol(selected, closes_by_symbol, lookback_bars)
    if weight_scheme == "inverse_vol":
        return _inverse_vol_weights(selected, vols)

    if weight_scheme in ("min_variance", "max_sharpe", "erc"):
        subset = {s: dict(closes_by_symbol.get(s, {})) for s in selected}
        member_vols = {s: vols.get(s) for s in selected}
        if weight_scheme == "min_variance":
            raw = min_variance_group_scales(
                subset, lookback_bars=lookback_bars, member_vols=member_vols
            )
        elif weight_scheme == "max_sharpe":
            raw = max_sharpe_group_scales(
                subset, lookback_bars=lookback_bars, member_vols=member_vols
            )
        else:
            raw = erc_group_scales(subset, lookback_bars=lookback_bars, member_vols=member_vols)
        # The optimizer can return weights for only a subset on partial data;
        # any selected name it omitted falls back to its inverse-vol weight so
        # the vector still covers every selected name before normalization.
        for s in selected:
            raw.setdefault(s, inverse_vol_group_scale(vols.get(s), list(vols.values())))
        return _normalize({s: raw[s] for s in selected})

    raise ValueError(f"unknown weight_scheme: {weight_scheme!r}")


# ----------------------------------------------------------------- planning


def _target_qty(target_dollar: Decimal, price: Decimal, *, lot_rounding: str = "floor") -> int:
    if price <= 0:
        return 0
    rounding = ROUND_FLOOR if lot_rounding == "floor" else ROUND_HALF_UP
    return int((target_dollar / price).to_integral_value(rounding=rounding))


def rebalance_plan(
    *,
    target_weights: Mapping[str, Decimal],
    holdings: Mapping[str, int],
    prices: Mapping[str, Decimal],
    capital_usd: Decimal,
    invested_fraction: Decimal = _ONE,
    rebalance_threshold_pct: Decimal = Decimal("0"),
    min_notional_usd: Decimal = Decimal("0"),
    mode: str = "rebalance",
    lot_rounding: str = "floor",
) -> list[PlannedOrder]:
    """Diff a target-weight vector against holdings into BUY/SELL orders.

    * A name held but NOT in ``target_weights`` is fully exited (SELL all) —
      regardless of the no-trade band — so a name that drops out of the top
      ranks is always cut (SC-05). This is the missing sell dimension.
    * ``mode="rebalance"`` (default): for a name in the target, the no-trade band
      (``rebalance_threshold_pct``, in percentage points of total capital)
      suppresses orders whose weight change is below the band, and
      ``min_notional_usd`` drops sub-threshold odd-lot trades — turnover controls
      so churn does not eat the alpha.
    * ``mode="hold_replace"``: low-turnover "let winners run" — only EXIT dropouts
      and BUY *new* entrants (names in the target not currently held); existing
      holdings are left untouched (no trim back to target weight). On real
      mega-cap data this avoided the winner-trimming + churn that made the default
      mode lose to buy-and-hold (see REAL-DATA-FINDINGS.md).

    Quantities are proposed only; the caller routes every BUY through the K1
    gate chain, which rejects anything over the caps. Deterministic: symbols are
    processed in sorted order.
    """
    if lot_rounding not in {"floor", "nearest"}:
        raise ValueError(f"unknown lot_rounding: {lot_rounding!r}")

    investable = capital_usd * invested_fraction
    orders: list[PlannedOrder] = []
    symbols = sorted(set(target_weights) | {s for s, q in holdings.items() if q})
    target_quantities: dict[str, int] = {}
    for symbol, weight in target_weights.items():
        price = prices.get(symbol)
        if price is not None and price > 0:
            target_quantities[symbol] = _target_qty(
                weight * investable, price, lot_rounding=lot_rounding
            )

    if lot_rounding == "nearest":
        target_notional = sum(
            Decimal(qty) * prices[symbol] for symbol, qty in target_quantities.items()
        )
        while target_notional > investable:
            candidates: list[tuple[Decimal, str]] = []
            for symbol, qty in target_quantities.items():
                if qty < 1:
                    continue
                price = prices[symbol]
                target_dollar = target_weights[symbol] * investable
                before = abs(Decimal(qty) * price - target_dollar)
                after = abs(Decimal(qty - 1) * price - target_dollar)
                candidates.append((after - before, symbol))
            if not candidates:
                break
            _, reduce_symbol = min(candidates)
            target_quantities[reduce_symbol] -= 1
            target_notional -= prices[reduce_symbol]

    for symbol in symbols:
        current_qty = holdings.get(symbol, 0)
        price = prices.get(symbol)
        weight = target_weights.get(symbol)

        # Exit: held but no longer a target -> sell the whole position.
        if weight is None:
            if current_qty > 0:
                orders.append(PlannedOrder(symbol, "SELL", current_qty))
            continue

        if price is None or price <= 0:
            continue  # cannot price a target buy/rebalance without a quote

        if mode == "hold_replace":
            # Let existing winners run: only buy *new* entrants, never trim/add to
            # a name already held. Exits above already handle rank dropouts.
            if current_qty > 0:
                continue
            target_qty = target_quantities.get(symbol, 0)
            if target_qty < 1:
                continue
            if min_notional_usd > 0 and Decimal(target_qty) * price < min_notional_usd:
                continue
            orders.append(PlannedOrder(symbol, "BUY", target_qty))
            continue

        target_dollar = weight * investable
        target_qty = target_quantities.get(symbol, 0)
        delta = target_qty - current_qty
        if delta == 0:
            continue

        # No-trade band: skip when the weight move is below the threshold.
        if rebalance_threshold_pct > 0 and capital_usd > 0:
            current_weight_pct = Decimal(current_qty) * price / capital_usd * Decimal(100)
            target_weight_pct = target_dollar / capital_usd * Decimal(100)
            if abs(target_weight_pct - current_weight_pct) < rebalance_threshold_pct:
                continue

        qty = abs(delta)
        if min_notional_usd > 0 and Decimal(qty) * price < min_notional_usd:
            continue

        orders.append(PlannedOrder(symbol, "BUY" if delta > 0 else "SELL", qty))

    return orders


__all__ = [
    "PlannedOrder",
    "rebalance_plan",
    "select_symbols",
    "target_weights",
]
