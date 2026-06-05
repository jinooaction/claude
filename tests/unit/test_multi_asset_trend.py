"""스펙 043 — 멀티에셋 분산 추세추종 단위 테스트."""

from __future__ import annotations

import math

from auto_invest.analytics.multi_asset_trend import (
    _par_bond_price,
    blend,
    bond_total_return_factors,
    carry_forward_rates,
    compare_diversified_trend,
    correlation,
    diversified_trend_factors,
    equity_trend_factors,
    risk_parity_diversified_factors,
    sleeve_factors,
    sma_in_market,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow, trend_in_market


def _rows(prices: list[float], *, div: float = 0.0, rate: float = 0.0) -> list[MonthlyRow]:
    return [
        MonthlyRow(
            date=f"20{1 + i // 12:02d}-{1 + i % 12:02d}-01",
            price=p,
            dividend=div,
            long_rate=rate,
        )
        for i, p in enumerate(prices)
    ]


def _rows_with_rates(prices: list[float], rates: list[float]) -> list[MonthlyRow]:
    return [
        MonthlyRow(date=f"20{1 + i // 12:02d}-{1 + i % 12:02d}-01", price=p, dividend=0.0,
                   long_rate=rt)
        for i, (p, rt) in enumerate(zip(prices, rates, strict=True))
    ]


# ───────────────────────────── 채권 가격/총수익 ─────────────────────────────


def test_par_bond_price_at_par_is_one():
    # 쿠폰==수익률(par 발행) → 가격 정확히 1.0.
    assert _par_bond_price(0.05, 0.05, 10) == 1.0
    assert _par_bond_price(0.03, 0.03, 10) == 1.0


def test_par_bond_price_falling_yield_rises():
    # 금리 하락(쿠폰 5% 채권을 4%로 평가) → 가격 > 1(듀레이션 이득).
    assert _par_bond_price(0.05, 0.04, 10) > 1.0


def test_par_bond_price_rising_yield_falls():
    # 금리 상승(쿠폰 5% 채권을 6%로 평가) → 가격 < 1.
    assert _par_bond_price(0.05, 0.06, 10) < 1.0


def test_bond_factor_flat_rate_is_pure_coupon():
    # 금리 불변이면 가격변화 0, 월 팩터 = 1 + y/12.
    rows = _rows_with_rates([100, 100, 100], [6.0, 6.0, 6.0])
    factors = bond_total_return_factors(rows)
    assert len(factors) == 2
    for f in factors:
        assert abs(f - (1.0 + 0.06 / 12)) < 1e-12


def test_bond_factor_falling_rate_beats_coupon():
    # 금리 하락(6→5%) 달의 총수익 > 순수 쿠폰(가격 상승분 추가).
    rows = _rows_with_rates([100, 100], [6.0, 5.0])
    f = bond_total_return_factors(rows)[0]
    assert f > 1.0 + 0.06 / 12


def test_bond_factor_zero_rate_is_cash():
    # 유효 금리가 아직 없으면(0) 현금(1.0).
    rows = _rows_with_rates([100, 100, 100], [0.0, 0.0, 0.0])
    assert bond_total_return_factors(rows) == [1.0, 1.0]


def test_carry_forward_rates_fills_missing():
    rows = _rows_with_rates([1, 2, 3, 4], [5.0, 0.0, 0.0, 4.0])
    assert carry_forward_rates(rows) == [5.0, 5.0, 5.0, 4.0]


def test_carry_forward_leading_zero_stays_zero():
    rows = _rows_with_rates([1, 2, 3], [0.0, 0.0, 3.0])
    assert carry_forward_rates(rows) == [0.0, 0.0, 3.0]


# ───────────────────────────── 일반 추세 신호 ─────────────────────────────


def test_sma_in_market_matches_trend_in_market_on_prices():
    # 가격 레벨에 적용하면 스펙 042 trend_in_market 와 동일해야 한다(일반화 정확성).
    prices = [10, 11, 12, 9, 8, 13, 14, 15]
    rows = _rows(prices)
    levels = [float(p) for p in prices]
    assert sma_in_market(levels, 3) == trend_in_market(rows, 3)


def test_sma_in_market_before_window_is_true():
    levels = [1.0, 2.0, 3.0]
    out = sma_in_market(levels, 5)  # 창보다 짧음 → 전부 True
    assert out == [True, True]


def test_sma_in_market_basic_logic():
    # 레벨 [10,12,8]: k=1 창부족 True; k=2 levels[1]=12 > SMA([10,12])=11 → True 아님?
    # 창=2: k=2 → SMA(levels[0:2])=11, levels[1]=12>11 → True.
    out = sma_in_market([10.0, 12.0, 8.0], 2)
    assert out == [True, True]
    # 하락: [10,12,8,6] 창2 → k=3 SMA(levels[1:3])=10, levels[2]=8<10 → False.
    out2 = sma_in_market([10.0, 12.0, 8.0, 6.0], 2)
    assert out2[-1] is False


# ───────────────────────────── 슬리브/블렌드 ─────────────────────────────


def test_sleeve_factors_picks_asset_or_cash():
    asset = [1.10, 0.90, 1.05]
    cash = [1.001, 1.001, 1.001]
    in_mkt = [True, False, True]
    assert sleeve_factors(asset, cash, in_mkt) == [1.10, 1.001, 1.05]


def test_blend_weighted_average():
    a = [1.10, 1.00]
    b = [1.00, 1.20]
    out = blend([(0.5, a), (0.5, b)])
    assert out == [1.05, 1.10]


def test_blend_respects_weights():
    a = [2.0, 2.0]
    b = [1.0, 1.0]
    assert blend([(0.6, a), (0.4, b)]) == [1.6, 1.6]


def test_blend_length_mismatch_raises():
    try:
        blend([(0.5, [1.0, 1.0]), (0.5, [1.0])])
    except ValueError:
        return
    raise AssertionError("length mismatch should raise")


# ───────────────────────────── 상관 ─────────────────────────────


def test_correlation_perfect_positive():
    a = [1.01, 1.02, 1.03, 1.04]
    b = [1.02, 1.04, 1.06, 1.08]  # 같은 방향 선형
    c = correlation(a, b)
    assert c is not None and abs(c - 1.0) < 1e-9


def test_correlation_perfect_negative():
    a = [1.01, 1.02, 1.03, 1.04]
    b = [1.04, 1.03, 1.02, 1.01]
    c = correlation(a, b)
    assert c is not None and abs(c + 1.0) < 1e-9


def test_correlation_zero_variance_none():
    a = [1.0, 1.0, 1.0]
    b = [1.01, 1.02, 1.03]
    assert correlation(a, b) is None


# ───────────────────────────── 통합 비교 ─────────────────────────────


def test_compare_diversified_trend_structure():
    # 합성: 주식은 변동 큰 추세, 채권은 금리 시계열. 구조/필드 존재만 검증(엣지 주장 아님).
    n = 60
    prices = [100 * (1.01 ** i) for i in range(n)]  # 꾸준한 상승
    rates = [5.0] * n
    rows = _rows_with_rates(prices, rates)
    cmp = compare_diversified_trend(rows, window=10, equity_weight=0.5, bond_weight=0.5)
    d = cmp.as_dict()
    assert set(d) >= {
        "window", "equity_weight", "bond_weight", "verdict", "reason",
        "bh_equity", "bh_6040", "trend_equity", "trend_bond", "diversified_trend",
    }
    assert cmp.verdict in {
        "DIVERSIFICATION_EDGE", "NO_DIVERSIFICATION_BENEFIT", "INSUFFICIENT",
    }
    # 모든 다리의 샤프가 유한.
    for leg in (cmp.bh_equity, cmp.diversified_trend, cmp.trend_bond):
        assert math.isfinite(leg.sharpe)


def test_factor_stream_helpers_length_and_finite():
    n = 60
    rows = _rows_with_rates([100 * (1.01 ** i) for i in range(n)], [5.0] * n)
    div = diversified_trend_factors(rows, window=10)
    eq = equity_trend_factors(rows, window=10)
    rp = risk_parity_diversified_factors(rows, window=10)
    assert len(div) == len(eq) == len(rp) == n - 1
    for f in div + eq + rp:
        assert math.isfinite(f) and f > 0


def test_risk_parity_no_lookahead_first_period_neutral():
    # 이력 부족(첫 기간)이면 50/50 중립 → diversified(50/50) 첫 값과 같아야 한다.
    n = 40
    rows = _rows_with_rates([100 * (1.005 ** i) for i in range(n)], [4.0] * n)
    rp = risk_parity_diversified_factors(rows, window=10, vol_window=12)
    div = diversified_trend_factors(rows, window=10, equity_weight=0.5, bond_weight=0.5)
    assert abs(rp[0] - div[0]) < 1e-12


def test_diversified_lower_vol_than_pure_equity_buyhold():
    # 분산(절반 현금/채권 가능)은 단순 보유 주식보다 변동성이 낮아야 한다(방어 본질).
    n = 80
    # 변동성 큰 주식(지그재그 상승) + 안정 채권.
    prices = []
    p = 100.0
    for i in range(n):
        p *= 1.03 if i % 2 == 0 else 0.99
        prices.append(p)
    rows = _rows_with_rates(prices, [4.0] * n)
    cmp = compare_diversified_trend(rows, window=10)
    assert cmp.diversified_trend.vol_pct < cmp.bh_equity.vol_pct
