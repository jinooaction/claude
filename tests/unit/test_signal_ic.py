"""스펙 041 — 정보계수(IC) 예측 성공률 측정 테스트."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.analytics.signal_ic import (
    cross_sectional_ic,
    spearman,
)
from auto_invest.market_data.store import PriceBar

# --------------------------------------------------------------- spearman


def test_spearman_perfect_positive():
    assert spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) == 1.0


def test_spearman_perfect_negative():
    assert spearman([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]) == -1.0


def test_spearman_monotone_nonlinear_is_one():
    # 스피어만은 순위만 보므로 비선형 단조도 1.
    assert spearman([1.0, 2.0, 3.0, 4.0], [1.0, 4.0, 9.0, 16.0]) == 1.0


def test_spearman_too_few_points_is_none():
    assert spearman([1.0, 2.0], [1.0, 2.0]) is None


def test_spearman_zero_variance_is_none():
    assert spearman([5.0, 5.0, 5.0, 5.0], [1.0, 2.0, 3.0, 4.0]) is None


# ----------------------------------------------------- cross_sectional_ic


def _series(symbol: str, growth: float, n: int = 40, base: float = 100.0) -> list[PriceBar]:
    """일정 일간 성장률 growth 의 종가 시계열(다른 종목은 다른 growth)."""
    bars = []
    price = base
    for i in range(n):
        price = price * (1.0 + growth)
        if i < 31:
            d = f"2026-01-{i + 1:02d}T00:00:00.000Z"
        else:
            d = f"2026-02-{i - 30:02d}T00:00:00.000Z"
        p = Decimal(str(round(price, 4)))
        bars.append(
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=d,
                open_usd=p,
                high_usd=p,
                low_usd=p,
                close_usd=p,
                volume=1_000_000,
            )
        )
    return bars


def test_ic_detects_predictive_signal():
    # 성장률이 높은 종목 = 모멘텀 높음 = forward 수익도 높음 → 점수와 미래수익 순위 완전일치.
    # 따라서 평균 IC ≈ +1, 예측력 있음으로 판정돼야 한다.
    growths = {"A": 0.001, "B": 0.004, "C": 0.007, "D": 0.010, "E": 0.013, "F": 0.016}
    symbol_bars = {s: _series(s, g) for s, g in growths.items()}
    result = cross_sectional_ic(
        symbol_bars,
        weights={"momentum": Decimal("1.0")},
        lookback_bars=5,
        momentum_period=3,
        forward_horizon=3,
        step=3,
        min_symbols=5,
    )
    assert result.n_dates >= 4
    assert result.mean_ic > 0.8  # 강한 양의 예측력
    assert result.hit_rate >= 0.9
    assert "예측력 있음" in result.verdict


def test_ic_insufficient_when_too_few_dates():
    # 바가 거의 없으면 측정 시점이 부족 → insufficient 판정.
    growths = {"A": 0.001, "B": 0.004, "C": 0.007, "D": 0.010, "E": 0.013}
    symbol_bars = {s: _series(s, g, n=8) for s, g in growths.items()}
    result = cross_sectional_ic(
        symbol_bars,
        weights={"momentum": Decimal("1.0")},
        lookback_bars=3,
        momentum_period=2,
        forward_horizon=5,
        step=5,
        min_symbols=5,
    )
    assert result.n_dates < 4
    assert "insufficient" in result.verdict


def test_ic_empty_universe():
    result = cross_sectional_ic(
        {}, weights={"momentum": Decimal("1.0")}, forward_horizon=3
    )
    assert result.n_dates == 0
    assert "insufficient" in result.verdict
