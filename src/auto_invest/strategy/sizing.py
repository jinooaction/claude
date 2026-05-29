"""Risk-based position sizing (spec 017) — volatility-aware quantity scaling.

NON-KERNEL. This module only ever *proposes* a quantity; the K1 position caps
(`risk/gates.py`) remain the inviolable ceiling and run unchanged after sizing.

  * Slice 1 — volatility *throttling* (down-only): scale the rule's declared base
    quantity DOWN when realized volatility exceeds the target, never up. This is
    the default (``max_scale`` defaults to 1).
  * Slice 2 — bidirectional volatility *targeting*: when the rule sets
    ``max_scale > 1`` a calm window (realized < target) scales the position UP
    toward the target risk budget, capped at ``max_scale``. The K1 caps still run
    unchanged after sizing and REJECT anything over the per-trade / per-symbol /
    global ceiling, so even upscaling can never lift exposure above the safety
    boundary — K1 is the true ceiling.
  * Slice 2b — inverse-volatility risk parity ACROSS a sizing group
    (``mode="inverse_vol"``): members of the same ``sizing_group`` are weighted
    by ``min(member vols) / own vol`` so the lowest-vol member keeps full size
    and higher-vol members shrink to balance per-share risk. Always down-only
    (weight <= 1), so K1 still binds below. The weight is computed by the caller
    (worker / replay) via ``build_sizing_groups`` + ``inverse_vol_group_scale``
    and passed in as ``group_scale``, so live and backtest share one yardstick.
  * Slice 3 — correlation haircut (opt-in ``correlation_haircut`` on an
    inverse_vol group member): when a member's returns are positively correlated
    with the rest of its basket (low diversification), its weight is shrunk
    further by ``1 - strength * avg_corr``. Always down-only, so it can only
    REDUCE a correlated/concentrated bet — a defensive risk control, not a
    return optimiser. ``group_scale_for`` composes the inverse-vol weight and the
    correlation haircut into one factor for both paths.

All math is deterministic Decimal (no float, no LLM) so the backtest replay
stays byte-equal across machines (FR-B15) and live trading uses the identical
sizing as the backtest (constitution X.2, single yardstick).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from auto_invest.config.rules import SizingConfig, TradingRule

# Volatility / scale are normalised to 6 decimals to match the rest of the
# backtest's byte-equality contract (see backtest/data_model.canonicalise_decimal).
_QUANT = Decimal("0.000001")


def _canon(value: Decimal) -> Decimal:
    return value.quantize(_QUANT)


def realized_volatility(closes: Sequence[Decimal]) -> Decimal | None:
    """Sample standard deviation of simple per-bar returns, as a fraction.

    Returns None when there are fewer than two returns (need >= 3 closes) or
    any close is non-positive (a return is undefined). The result is a fraction
    (e.g. ``Decimal("0.015")`` for 1.5% per-bar volatility), normalised to 6 dp.
    """
    if len(closes) < 3:
        return None
    returns: list[Decimal] = []
    prev = closes[0]
    if prev <= 0:
        return None
    for close in closes[1:]:
        if close <= 0:
            return None
        returns.append(close / prev - Decimal(1))
        prev = close
    n = Decimal(len(returns))
    mean = sum(returns, Decimal(0)) / n
    # Sample variance (n-1 denominator). len(returns) >= 2 here.
    variance = sum(((r - mean) ** 2 for r in returns), Decimal(0)) / (n - Decimal(1))
    if variance <= 0:
        return Decimal(0)
    return _canon(variance.sqrt())


def volatility_scale(
    realized: Decimal,
    target: Decimal,
    *,
    min_scale: Decimal = Decimal(0),
    max_scale: Decimal = Decimal(1),
) -> Decimal:
    """Volatility-targeting factor in ``[min_scale, max_scale]``.

    ``target / realized`` clamped to ``[min_scale, max_scale]``. With the default
    ``max_scale=1`` this is the slice-1 down-only throttle — the factor never
    exceeds 1, so the position is never sized above the declared base. With
    ``max_scale > 1`` it becomes bidirectional volatility targeting: a calm
    window (realized < target) scales the position UP toward the target risk
    budget, still capped at ``max_scale`` (and, at the order layer, by the
    unchanged K1 caps). A non-positive realized volatility means "no reliable
    measurement to act on", so the factor is the neutral 1 (neither throttle nor
    amplify).
    """
    if realized <= 0:
        return Decimal(1)
    raw = target / realized
    if raw > max_scale:
        raw = max_scale
    if raw < min_scale:
        raw = min_scale
    return _canon(raw)


@dataclass(frozen=True)
class SizingGroupMember:
    """One member of a sizing group (slice 2b).

    Carries just enough to re-measure the member's realized volatility
    identically in both the live router and the backtest replay (constitution
    X.2 single yardstick): the symbol, its bar timeframe, and the lookback.
    """

    rule_id: str
    symbol: str
    timeframe: str
    lookback_bars: int


def build_sizing_groups(
    rules: Sequence[TradingRule],
) -> dict[str, list[SizingGroupMember]]:
    """Map each ``sizing_group`` name to its enabled ``inverse_vol`` members.

    Only enabled rules whose sizing mode is "inverse_vol" participate. The worker
    and the replay engine build this from the SAME static rule set, so both
    derive identical inverse-vol weights (single yardstick).
    """
    groups: dict[str, list[SizingGroupMember]] = {}
    for rule in rules:
        sizing = rule.sizing
        if (
            not rule.enabled
            or rule.sizing_group is None
            or sizing is None
            or sizing.mode != "inverse_vol"
        ):
            continue
        timeframe = getattr(rule.trigger, "timeframe", "1d")
        groups.setdefault(rule.sizing_group, []).append(
            SizingGroupMember(
                rule_id=rule.id,
                symbol=rule.symbol,
                timeframe=timeframe,
                lookback_bars=sizing.lookback_bars,
            )
        )
    return groups


def inverse_vol_group_scale(
    own_vol: Decimal | None,
    member_vols: Sequence[Decimal | None],
) -> Decimal:
    """Down-only inverse-volatility (risk-parity) weight for one group member.

    Returns ``min(measurable member vols) / own_vol`` clamped to ``(0, 1]``.
    ``member_vols`` is the whole group including this member. The lowest-vol
    member keeps full size (weight 1); higher-vol members shrink so each
    contributes balanced per-share risk. Fail-safe: own vol unmeasurable
    (None / <= 0) or no measurable member -> 1 (no group throttle). The result is
    always <= 1, so grouping can only REDUCE exposure vs the declared base — K1
    still binds below and the slice-1 down-only invariant holds.
    """
    if own_vol is None or own_vol <= 0:
        return Decimal(1)
    measurable = [v for v in member_vols if v is not None and v > 0]
    if not measurable:
        return Decimal(1)
    scale = min(measurable) / own_vol
    if scale > 1:
        scale = Decimal(1)
    return _canon(scale)


def _returns(closes: Sequence[Decimal]) -> list[Decimal] | None:
    """Simple per-bar returns ``cᵢ/cᵢ₋₁ - 1``; None if < 2 closes or any <= 0."""
    if len(closes) < 2:
        return None
    out: list[Decimal] = []
    prev = closes[0]
    if prev <= 0:
        return None
    for close in closes[1:]:
        if close <= 0:
            return None
        out.append(close / prev - Decimal(1))
        prev = close
    return out


def pearson_correlation(
    xs: Sequence[Decimal], ys: Sequence[Decimal]
) -> Decimal | None:
    """Pearson correlation of two equal-length return series (Decimal).

    Returns None when there are fewer than two points, the lengths differ, or
    either series has zero variance (correlation undefined).
    """
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    nn = Decimal(n)
    mx = sum(xs, Decimal(0)) / nn
    my = sum(ys, Decimal(0)) / nn
    cov = sum(((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)), Decimal(0))
    vx = sum(((x - mx) ** 2 for x in xs), Decimal(0))
    vy = sum(((y - my) ** 2 for y in ys), Decimal(0))
    if vx <= 0 or vy <= 0:
        return None
    return _canon(cov / (vx * vy).sqrt())


def average_correlations(
    closes_by_rule: Mapping[str, Mapping[date, Decimal]],
    *,
    lookback_bars: int,
) -> dict[str, Decimal | None]:
    """For each rule, the mean Pearson correlation of its recent returns with
    each peer's, over the group's COMMON trading days.

    Aligns members on the intersection of their bar dates (deterministic, the
    same in live and backtest), takes the most recent ``lookback_bars + 1``
    common closes, and correlates the resulting returns pairwise. A rule's value
    is None (no measurable concentration) when there are < 3 common days or no
    peer pair has a defined correlation.
    """
    rule_ids = list(closes_by_rule)
    if not rule_ids:
        return {}
    common: set[date] = set.intersection(
        *(set(closes_by_rule[r].keys()) for r in rule_ids)
    )
    window = sorted(common)[-(lookback_bars + 1) :]
    returns_by_rule: dict[str, list[Decimal] | None] = {
        r: _returns([closes_by_rule[r][d] for d in window]) for r in rule_ids
    }
    result: dict[str, Decimal | None] = {}
    for r in rule_ids:
        own = returns_by_rule[r]
        if own is None:
            result[r] = None
            continue
        corrs = [
            c
            for p in rule_ids
            if p != r and returns_by_rule[p] is not None
            for c in (pearson_correlation(own, returns_by_rule[p]),)
            if c is not None
        ]
        result[r] = _canon(sum(corrs, Decimal(0)) / Decimal(len(corrs))) if corrs else None
    return result


def correlation_haircut(avg_corr: Decimal | None, strength: Decimal) -> Decimal:
    """Down-only haircut ``1 - strength * max(0, avg_corr)`` in ``[0, 1]``.

    No haircut (1) when there is no measurable correlation, the strength is 0,
    or the basket is diversified / anti-correlated (avg_corr <= 0). A positively
    correlated (concentrated) member is shrunk toward 0 as correlation and
    strength rise — never sized up.
    """
    if avg_corr is None or strength <= 0:
        return Decimal(1)
    positive = avg_corr if avg_corr > 0 else Decimal(0)
    g = Decimal(1) - strength * positive
    if g < 0:
        g = Decimal(0)
    if g > 1:
        g = Decimal(1)
    return _canon(g)


def group_scale_for(
    rule_id: str,
    *,
    member_vols: Mapping[str, Decimal | None],
    closes_by_rule: Mapping[str, Mapping[date, Decimal]] | None,
    lookback_bars: int,
    correlation_strength: Decimal = Decimal(0),
) -> Decimal:
    """Combined down-only group weight for ``rule_id``: inverse-vol weight
    (slice 2b) times the correlation haircut (slice 3).

    Both factors are <= 1, so the product is <= 1 — grouping can only reduce
    exposure vs the declared base. Both the live router and the backtest replay
    call this with the same gathered inputs, so live and backtest agree
    (constitution X.2). When ``correlation_strength`` is 0 (or no closes are
    supplied) only the inverse-vol weight applies (byte-equal to slice 2b).
    """
    iv = inverse_vol_group_scale(
        member_vols.get(rule_id), list(member_vols.values())
    )
    if correlation_strength <= 0 or not closes_by_rule:
        return iv
    avg = average_correlations(closes_by_rule, lookback_bars=lookback_bars).get(rule_id)
    return _canon(iv * correlation_haircut(avg, correlation_strength))


@dataclass(frozen=True)
class SizingResult:
    """Full sizing decision record for audit and observability (spec 018)."""

    base_qty: int
    final_qty: int
    sizing_mode: str
    realized_vol_pct: Decimal | None = None
    vol_scale: Decimal | None = None
    group_scale: Decimal = Decimal(1)


def sized_quantity_with_result(
    *,
    base_qty: int,
    closes: Sequence[Decimal],
    sizing: SizingConfig | None,
    group_scale: Decimal = Decimal(1),
) -> SizingResult:
    """Like ``sized_quantity`` but returns a ``SizingResult`` with full context.

    Intended for order_router — the result fields feed the SIZING_DECISION audit
    row so every sizing decision is forensically reproducible.
    """
    mode = "fixed" if sizing is None else sizing.mode

    if sizing is None or sizing.mode == "fixed":
        return SizingResult(
            base_qty=base_qty,
            final_qty=base_qty,
            sizing_mode=mode,
            group_scale=Decimal(1),
        )

    if sizing.mode == "inverse_vol":
        scaled = (Decimal(base_qty) * group_scale).to_integral_value(rounding=ROUND_FLOOR)
        final = max(0, int(scaled))
        return SizingResult(
            base_qty=base_qty,
            final_qty=final,
            sizing_mode=mode,
            group_scale=group_scale,
        )

    # target_vol path
    window = list(closes)[-(sizing.lookback_bars + 1) :]
    realized = realized_volatility(window)
    if realized is None:
        return SizingResult(
            base_qty=base_qty,
            final_qty=base_qty,
            sizing_mode=mode,
            group_scale=Decimal(1),
        )
    target = sizing.target_volatility_pct / Decimal(100)
    scale = volatility_scale(
        realized, target, min_scale=sizing.min_scale, max_scale=sizing.max_scale
    )
    scaled = (Decimal(base_qty) * scale).to_integral_value(rounding=ROUND_FLOOR)
    final = max(0, int(scaled))
    return SizingResult(
        base_qty=base_qty,
        final_qty=final,
        sizing_mode=mode,
        realized_vol_pct=_canon(realized * Decimal(100)),
        vol_scale=scale,
        group_scale=Decimal(1),
    )


def sized_quantity(
    *,
    base_qty: int,
    closes: Sequence[Decimal],
    sizing: SizingConfig | None,
    group_scale: Decimal = Decimal(1),
) -> int:
    """Final integer quantity after volatility-based sizing.

    When ``sizing`` is None or mode="fixed" the declared ``base_qty`` is returned
    unchanged (v1 behaviour, byte-equal). For mode="target_vol" the most recent
    ``lookback_bars`` returns set the realized volatility; if it cannot be
    measured the base qty is returned (fail-safe, FR-S04). Otherwise the base is
    scaled by ``volatility_scale`` — DOWN by default, or UP toward the target
    risk budget when the rule sets ``max_scale > 1`` (slice 2). For
    mode="inverse_vol" the base is scaled by ``group_scale`` (slice 2b), the
    inverse-vol group weight the caller computed via ``inverse_vol_group_scale``;
    ``group_scale`` is always <= 1. The result is floored (never rounded up) and
    may be 0, which callers treat as "skip this fill" (FR-S05). K1 caps run
    unchanged after sizing, so they remain the true ceiling.
    """
    if sizing is None or sizing.mode == "fixed":
        return base_qty

    if sizing.mode == "inverse_vol":
        # Slice 2b: the caller measured the group's vols and passed the down-only
        # weight as group_scale (default 1 = no group context -> base, fail-safe).
        scaled = (Decimal(base_qty) * group_scale).to_integral_value(
            rounding=ROUND_FLOOR
        )
        result = int(scaled)
        return result if result > 0 else 0

    # Need lookback returns -> lookback + 1 closes; take the most recent tail.
    window = list(closes)[-(sizing.lookback_bars + 1) :]
    realized = realized_volatility(window)
    if realized is None:
        return base_qty  # fail-safe: not enough data to size

    target = sizing.target_volatility_pct / Decimal(100)
    scale = volatility_scale(
        realized, target, min_scale=sizing.min_scale, max_scale=sizing.max_scale
    )
    scaled = (Decimal(base_qty) * scale).to_integral_value(rounding=ROUND_FLOOR)
    result = int(scaled)
    return result if result > 0 else 0


class ERCConvergenceError(RuntimeError):
    """ERC 반복 최적화가 수렴하지 않았을 때 발생."""


def covariance_matrix(
    closes_by_rule: Mapping[str, Mapping[date, Decimal]],
    *,
    lookback_bars: int,
) -> list[list[Decimal]] | None:
    """자산 간 표본 공분산 행렬 (Decimal, 6자리 정규화).

    공통 날짜 교집합의 최근 ``lookback_bars + 1`` 봉을 쓴다.
    공통일 < 30이면 None 반환(데이터 부족).
    """
    rule_ids = list(closes_by_rule)
    n = len(rule_ids)
    if n == 0:
        return None
    common: set[date] = set.intersection(
        *(set(closes_by_rule[r].keys()) for r in rule_ids)
    )
    window = sorted(common)[-(lookback_bars + 1):]
    if len(window) < 30:
        return None
    # 수익률 행렬 (n × T)
    ret_matrix: list[list[Decimal]] = []
    for r in rule_ids:
        rets = _returns([closes_by_rule[r][d] for d in window])
        if rets is None:
            return None
        ret_matrix.append(rets)
    t = Decimal(len(ret_matrix[0]))
    means = [sum(row, Decimal(0)) / t for row in ret_matrix]
    cov: list[list[Decimal]] = []
    for i in range(n):
        row_i = [ret_matrix[i][k] - means[i] for k in range(int(t))]
        cov_row: list[Decimal] = []
        for j in range(n):
            row_j = [ret_matrix[j][k] - means[j] for k in range(int(t))]
            cij = sum((row_i[k] * row_j[k] for k in range(int(t))), Decimal(0)) / (t - 1)
            cov_row.append(_canon(cij))
        cov.append(cov_row)
    return cov


def erc_weights(
    cov_matrix: list[list[Decimal]],
    *,
    tol: float = 1e-8,
    max_iter: int = 500,
) -> list[Decimal]:
    """완전 공분산 ERC 가중치 (Maillard 2010 방법론).

    각 자산의 marginal risk contribution 이 동일하도록 반복 최적화.
    합산 1.0 으로 정규화. 수렴 실패 시 ``ERCConvergenceError``.
    결과는 down-only 보장을 위해 max 1 로 클램핑.
    """
    n = len(cov_matrix)
    if n == 0:
        raise ERCConvergenceError("빈 공분산 행렬")
    # float 로 반복, 마지막에 Decimal 변환
    cov_f = [[float(cov_matrix[i][j]) for j in range(n)] for i in range(n)]
    w = [1.0 / n] * n

    def portfolio_vol(weights: list[float]) -> float:
        var = sum(
            weights[i] * weights[j] * cov_f[i][j]
            for i in range(n)
            for j in range(n)
        )
        return math.sqrt(max(var, 0.0))

    def marginal_risk(weights: list[float], pv: float) -> list[float]:
        if pv <= 0:
            return [0.0] * n
        mrc = [
            sum(weights[j] * cov_f[i][j] for j in range(n)) / pv
            for i in range(n)
        ]
        return mrc

    for _iter in range(max_iter):
        pv = portfolio_vol(w)
        if pv <= 0:
            break
        mrc = marginal_risk(w, pv)
        rc = [w[i] * mrc[i] for i in range(n)]
        rc_sum = sum(rc)
        if rc_sum <= 0:
            break
        # CCD(순환 좌표 하강) 제곱근 업데이트 — 더 빠른 수렴
        new_w = w[:]
        for i in range(n):
            ri = rc[i]
            if ri > 0:
                new_w[i] = w[i] * math.sqrt((rc_sum / n) / ri)
        total = sum(new_w)
        if total <= 0:
            break
        new_w = [wi / total for wi in new_w]
        diff = max(abs(new_w[i] - w[i]) for i in range(n))
        w = new_w
        if diff < tol:
            break
    else:
        raise ERCConvergenceError(f"ERC 최적화가 {max_iter}회 내에 수렴하지 않았습니다.")

    raw = [Decimal(str(round(wi, 9))) for wi in w]
    # down-only: max 1 클램핑
    clamped = [min(r, Decimal(1)) for r in raw]
    return [_canon(r) for r in clamped]


def erc_group_scales(
    closes_by_rule: Mapping[str, Mapping[date, Decimal]],
    *,
    lookback_bars: int,
    member_vols: Mapping[str, Decimal | None],
) -> dict[str, Decimal]:
    """ERC 가중치 딕셔너리 반환. 데이터 부족 시 역변동성 fallback.

    rule_id → 가중치(Decimal, 0..1).
    """
    rule_ids = list(closes_by_rule)
    cov = covariance_matrix(closes_by_rule, lookback_bars=lookback_bars)
    if cov is not None:
        try:
            weights = erc_weights(cov)
            return {rule_ids[i]: weights[i] for i in range(len(rule_ids))}
        except ERCConvergenceError:
            pass
    # fallback: 역변동성 가중치
    return {
        r: inverse_vol_group_scale(member_vols.get(r), list(member_vols.values()))
        for r in rule_ids
    }


__all__ = [
    "ERCConvergenceError",
    "SizingGroupMember",
    "SizingResult",
    "average_correlations",
    "build_sizing_groups",
    "covariance_matrix",
    "correlation_haircut",
    "erc_group_scales",
    "erc_weights",
    "group_scale_for",
    "inverse_vol_group_scale",
    "pearson_correlation",
    "realized_volatility",
    "sized_quantity",
    "sized_quantity_with_result",
    "volatility_scale",
]
