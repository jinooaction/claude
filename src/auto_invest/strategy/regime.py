"""Regime detection — spec 019 슬라이스 1.

3상태 레짐(추세/횡보/하락)을 감지해 신호 강도 배율을 결정한다.

  * TRENDING  — ``close > SMA(50)`` AND ``SMA(50) > SMA(200)`` (골든크로스 상태)
  * BEAR      — ``close < SMA(200)`` AND ``close < SMA(50)``  (장·중기 이평 아래)
  * RANGING   — 그 외 (두 조건 모두 해당 안 됨)

입력은 마켓 인덱스(KOSPI 200, SPY 등) 대표 봉 시계열이다.
200막대 미만이면 RANGING 반환(fail-safe).

비커널 — K1 caps 은 이 모듈을 호출한 뒤에도 변경 없이 작동한다.
모든 계산은 결정론적 Decimal(float 없음)이므로 백테스트와 라이브가 같은 결과를 낸다.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.indicators import sma


class Regime(StrEnum):
    TRENDING = "trending"
    RANGING = "ranging"
    BEAR = "bear"


# 레짐별 기본 신호 배율 (YAML 룰셋으로 오버라이드 가능)
DEFAULT_REGIME_SCALE: dict[Regime, Decimal] = {
    Regime.TRENDING: Decimal("1.0"),
    Regime.RANGING: Decimal("0.7"),
    Regime.BEAR: Decimal("0.3"),
}

_MIN_BARS_FULL = 200
_SMA_SLOW = 200
_SMA_FAST = 50


def detect(bars: list[PriceBar]) -> Regime:
    """최신 봉 기준으로 레짐을 판별한다.

    200막대 미만이면 데이터 부족 → RANGING (fail-safe).
    """
    if len(bars) < _MIN_BARS_FULL:
        return Regime.RANGING

    close = bars[-1].close_usd
    slow = sma(bars, _SMA_SLOW)
    fast = sma(bars, _SMA_FAST)

    if close < slow and close < fast:
        return Regime.BEAR
    if close > fast and fast > slow:
        return Regime.TRENDING
    return Regime.RANGING


def apply_regime_scale(qty: int, scale: Decimal) -> int:
    """qty × scale 을 내림 정수로 반환. qty=0 이면 0."""
    if qty == 0:
        return 0
    result = (Decimal(qty) * scale).to_integral_value(rounding=ROUND_FLOOR)
    val = int(result)
    return val if val > 0 else 0


__all__ = [
    "DEFAULT_REGIME_SCALE",
    "Regime",
    "apply_regime_scale",
    "detect",
]
