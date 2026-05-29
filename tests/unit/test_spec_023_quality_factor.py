"""스펙 023 — 가격 기반 퀄리티 팩터 단위/통합 테스트.

검증 대상:
  SC-01: 안정적 상승 종목이 변동성 높은 종목보다 높은 퀄리티 점수
  SC-02: 데이터 부족(< 30봉) → Decimal("-Inf") 반환
  SC-03: 드로다운 없는 종목 점수 > 드로다운 큰 종목
  SC-04: quality_ranked 결과는 내림차순 정렬
  SC-05: QualityFilter.qualifies top_n 동작
  SC-06: QualityFilter.qualifies top_pct 동작
  SC-07: mode="quality_filter" 옵트인 — quality_filter=None 이면 기존 경로 byte 동일
  SC-08: top_n/top_pct 둘 다 설정 시 ValidationError 발생
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.quality import price_quality_score, quality_ranked

# =========================================================================== #
# 헬퍼                                                                         #
# =========================================================================== #


def _make_bars(prices: list[float], start: date | None = None) -> list[PriceBar]:
    if start is None:
        start = date(2024, 1, 2)
    bars = []
    for i, p in enumerate(prices):
        d = start + timedelta(days=i)
        bars.append(
            PriceBar(
                symbol="TEST",
                timeframe="1d",
                bar_open_utc=d.isoformat(),
                open_usd=Decimal(str(p)),
                high_usd=Decimal(str(p * 1.005)),
                low_usd=Decimal(str(p * 0.995)),
                close_usd=Decimal(str(p)),
                volume=1000,
            )
        )
    return bars


def _ramp(start: float, step: float, n: int) -> list[float]:
    return [start + step * i for i in range(n)]


def _volatile(base: float, amp: float, n: int) -> list[float]:
    result = []
    v = base
    for i in range(n):
        v = v + amp if i % 2 == 0 else v - amp
        result.append(max(v, 1.0))
    return result


def _with_drawdown(n: int, peak_at: int, drawdown_pct: float) -> list[float]:
    """peak_at 이후 drawdown_pct% 낙폭 후 회복 없이 유지."""
    prices = [100.0] * n
    peak = 110.0
    for i in range(n):
        if i < peak_at:
            prices[i] = 100.0 + (peak - 100.0) * i / peak_at
        else:
            prices[i] = peak * (1.0 - drawdown_pct / 100.0)
    return prices


# =========================================================================== #
# SC-01: 안정적 상승 종목 > 변동성 높은 종목                                    #
# =========================================================================== #


def test_quality_score_prefers_stable_uptrend():
    """완만하게 오르는 종목이 변동성 크고 드로다운 있는 종목보다 높은 점수."""
    n = 60
    stable_bars = _make_bars(_ramp(100.0, 0.3, n + 1))
    volatile_bars = _make_bars(_volatile(100.0, 8.0, n + 1))

    score_stable = price_quality_score(stable_bars, lookback_bars=n)
    score_volatile = price_quality_score(volatile_bars, lookback_bars=n)

    assert score_stable > score_volatile, (
        f"안정 점수({score_stable}) > 변동 점수({score_volatile}) 기대"
    )


# =========================================================================== #
# SC-02: 데이터 부족 → Decimal("-Inf")                                        #
# =========================================================================== #


def test_quality_score_insufficient_data_returns_sentinel():
    """봉 수가 30 미만이면 Decimal('-Inf')를 반환해야 한다."""
    bars = _make_bars(_ramp(100.0, 0.5, 20))  # 20봉 < 30
    score = price_quality_score(bars, lookback_bars=20)
    assert score == Decimal("-Inf"), f"데이터 부족 → -Inf 기대, 실제: {score}"


# =========================================================================== #
# SC-03: 드로다운 없는 종목 > 드로다운 큰 종목                                  #
# =========================================================================== #


def test_quality_score_penalises_large_drawdown():
    """최대 드로다운 30%인 종목보다 드로다운 없는 종목이 점수 높아야 한다."""
    n = 60
    no_dd = _make_bars(_ramp(100.0, 0.5, n + 1))
    big_dd = _make_bars(_with_drawdown(n + 1, peak_at=30, drawdown_pct=30.0))

    score_no_dd = price_quality_score(no_dd, lookback_bars=n)
    score_big_dd = price_quality_score(big_dd, lookback_bars=n)

    assert score_no_dd > score_big_dd, (
        f"드로다운 없는 점수({score_no_dd}) > 드로다운 있는 점수({score_big_dd}) 기대"
    )


# =========================================================================== #
# SC-04: quality_ranked — 내림차순 정렬                                        #
# =========================================================================== #


def test_quality_ranked_descending_order():
    """quality_ranked 결과는 점수 내림차순이어야 한다."""
    n = 60
    symbol_bars = {
        "stable": _make_bars(_ramp(100.0, 0.3, n + 1)),
        "volatile": _make_bars(_volatile(100.0, 6.0, n + 1)),
        "crash": _make_bars(_with_drawdown(n + 1, peak_at=20, drawdown_pct=40.0)),
    }
    ranked = quality_ranked(symbol_bars, lookback_bars=n)

    assert len(ranked) == 3
    scores = [s for _, s in ranked]
    for i in range(len(scores) - 1):
        if scores[i] != Decimal("-Inf") and scores[i + 1] != Decimal("-Inf"):
            assert scores[i] >= scores[i + 1], f"정렬 오류: {scores[i]} < {scores[i+1]}"

    # 'stable'이 1위여야 한다
    assert ranked[0][0] == "stable", f"1위 심볼 'stable' 기대, 실제: {ranked[0][0]}"


# =========================================================================== #
# SC-05: QualityFilter.qualifies — top_n                                      #
# =========================================================================== #


def test_quality_filter_qualifies_top_n():
    """top_n=1 이면 1위 종목만 통과, 나머지는 차단."""
    from auto_invest.config.rules import QualityFilter

    qf = QualityFilter(universe=("A", "B", "C"), top_n=1)
    ranked = [("A", Decimal("2.0")), ("B", Decimal("1.0")), ("C", Decimal("0.5"))]

    assert qf.qualifies("A", ranked) is True
    assert qf.qualifies("B", ranked) is False
    assert qf.qualifies("C", ranked) is False


# =========================================================================== #
# SC-06: QualityFilter.qualifies — top_pct                                   #
# =========================================================================== #


def test_quality_filter_qualifies_top_pct():
    """top_pct=50 이면 상위 50% (5심볼 중 3개 = ceil(5*0.5)=3) 통과."""
    from auto_invest.config.rules import QualityFilter

    qf = QualityFilter(universe=("A", "B", "C", "D", "E"), top_pct=50.0)
    ranked = [
        ("A", Decimal("5.0")),
        ("B", Decimal("4.0")),
        ("C", Decimal("3.0")),
        ("D", Decimal("2.0")),
        ("E", Decimal("1.0")),
    ]
    # ceil(5 * 50 / 100) = ceil(2.5) = 3
    assert qf.qualifies("A", ranked) is True
    assert qf.qualifies("B", ranked) is True
    assert qf.qualifies("C", ranked) is True
    assert qf.qualifies("D", ranked) is False
    assert qf.qualifies("E", ranked) is False


# =========================================================================== #
# SC-07: 옵트인 — quality_filter=None 이면 기존 경로 byte 동일                 #
# =========================================================================== #


def test_quality_filter_is_opt_in():
    """TradingRule.quality_filter=None 이 유효하고 기본값이어야 한다."""
    from auto_invest.config.rules import TradingRule

    rule = TradingRule(
        id="test_rule",
        symbol="AAPL",
        stage="BACKTEST",
        priority=0,
        trigger={"kind": "price", "direction": "<=", "threshold": "150.00", "cooldown_seconds": 0},
        action={"side": "BUY", "order_type": "LIMIT", "qty": 10, "limit_price": "149.00"},
    )
    assert rule.quality_filter is None


# =========================================================================== #
# SC-08: top_n과 top_pct 동시 설정 → ValidationError                         #
# =========================================================================== #


def test_quality_filter_rejects_both_top_n_and_top_pct():
    """top_n과 top_pct 둘 다 설정하면 ValidationError가 발생해야 한다."""
    from pydantic import ValidationError

    from auto_invest.config.rules import QualityFilter

    with pytest.raises(ValidationError):
        QualityFilter(universe=("A", "B"), top_n=1, top_pct=50.0)
