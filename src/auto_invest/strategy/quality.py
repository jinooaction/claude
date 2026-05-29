"""가격 기반 퀄리티 팩터 필터 (스펙 023).

KIS API 재무 데이터 없이 순수 가격 시계열로 퀄리티를 측정한다.

퀄리티 점수 = 롤링 샤프 비율 / (1 + |최대 드로다운 비율|)

- 롤링 샤프: annualised(mean(r) / std(r)) — 수익 대비 변동성 효율
- 최대 드로다운 비율: (peak − trough) / peak — 손실 내성

두 지표를 합성해 "수익을 내면서 덜 다치는" 종목을 높이 평가한다.
하향 전용 필터: 통과 못한 종목을 건너뛸 뿐 수량을 올리지 않으므로 K1 불변.

NON-KERNEL.
"""

from __future__ import annotations

import math
from decimal import Decimal

from auto_invest.market_data.store import PriceBar

_SENTINEL = Decimal("-Inf")
_MIN_BARS = 30


def _log_returns(bars: list[PriceBar]) -> list[float]:
    """연속 로그 수익률 리스트."""
    result = []
    for i in range(1, len(bars)):
        prev = float(bars[i - 1].close_usd)
        curr = float(bars[i].close_usd)
        if prev > 0 and curr > 0:
            result.append(math.log(curr / prev))
    return result


def _max_drawdown_ratio(bars: list[PriceBar]) -> float:
    """최고점 대비 최대 낙폭 비율 (0 ~ 1). 낙폭 없으면 0."""
    peak = float(bars[0].close_usd)
    max_dd = 0.0
    for bar in bars[1:]:
        price = float(bar.close_usd)
        if price > peak:
            peak = price
        if peak > 0:
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def price_quality_score(
    bars: list[PriceBar],
    *,
    lookback_bars: int = 60,
    annualise_factor: float = 252.0,
) -> Decimal:
    """가격 기반 퀄리티 점수.

    ``lookback_bars`` 개 봉을 사용해 롤링 샤프와 최대 드로다운을 계산한다.
    데이터 부족(< _MIN_BARS) 이면 ``Decimal("-Inf")`` (항상 하위 랭크).

    반환값은 Decimal(6자리 반올림).
    """
    window = bars[-lookback_bars:] if len(bars) >= lookback_bars else bars
    if len(window) < _MIN_BARS:
        return _SENTINEL

    rets = _log_returns(window)
    if len(rets) < 2:
        return _SENTINEL

    n = len(rets)
    mean_r = sum(rets) / n
    variance = sum((r - mean_r) ** 2 for r in rets) / (n - 1)
    if variance <= 0.0:
        return _SENTINEL

    sharpe = mean_r / math.sqrt(variance) * math.sqrt(annualise_factor)
    max_dd = _max_drawdown_ratio(window)

    score = sharpe / (1.0 + abs(max_dd))
    return Decimal(str(round(score, 6)))


def quality_ranked(
    symbol_bars: dict[str, list[PriceBar]],
    *,
    lookback_bars: int = 60,
) -> list[tuple[str, Decimal]]:
    """유니버스 전체를 퀄리티 점수로 내림차순 순위 매긴다.

    데이터 부족 심볼은 ``Decimal("-Inf")`` 로 마지막에 위치.
    동점 시 심볼명 알파벳 순 (결정론적 정렬).
    """
    scored: list[tuple[str, Decimal]] = []
    for symbol, bars in symbol_bars.items():
        score = price_quality_score(bars, lookback_bars=lookback_bars)
        scored.append((symbol, score))

    scored.sort(key=lambda t: (float(t[1]), t[0]), reverse=True)
    return scored
