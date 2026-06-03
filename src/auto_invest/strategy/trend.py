"""스펙 036 — 절대 모멘텀 추세 필터 (드로다운 방어 오버레이, 순수·결정론).

이 시스템의 반복된 정직한 결론(`REAL-DATA-FINDINGS.md`)은 세 가지 실패였다:
① 잦은 재조정의 회전율·비용이 수익을 잠식, ② 목표 비중 되돌리기가 강세장에서 승자를
덜어냄, ③ 좁은 유니버스. 그런데 알파 스택 전체에 **유일하게 빠진 전략 범주**가 있다 —
**종목별 절대 모멘텀(시계열 추세) 게이트**: 자기 추세 위에 있을 때만 보유하고, 아래로
내려가면 **현금으로 빠진다.**

이건 소매 시스템이 단순 보유 대비 *실제로 가치를 더하는* 지점이다. 강세장 raw 수익을
이기는 게 아니라(거의 불가능), **드로다운을 막아 위험조정 수익(샤프·칼마)을 한 사이클에
걸쳐 올린다.** 학술적으로도 가장 강건하게 복제된 소매 전략이다(Faber GTAA, Antonacci
듀얼 모멘텀). 그리고 세 실패를 정면으로 푼다:
  - 회전율 낮음(신호가 드물게 바뀜),
  - 승자를 안 덜어냄(보유/현금 이진 — 목표 비중 되돌리기 아님),
  - 드로다운 방어(폭락 전/중 현금으로 이탈).

설계 원칙:
  - 순수 함수. 외부 의존성 0(Decimal·stdlib 만). 같은 입력 → 같은 결과(백테스트=라이브).
  - 가산·옵트인. 필터를 끄면(spec None) 가중치는 손도 안 댄다(기존 동작 byte 동일).
  - **재정규화 안 함**: 추세 아래 종목을 0으로 만들면 합이 1 미만이 되고, 그 차이는
    자동으로 현금이다(Faber식 "보유 또는 현금"). 남은 종목으로 몰아주지 않는다 —
    몰아주면 소수 종목에 집중돼 오히려 위험이 커진다.
  - 보수적 fail-safe: 데이터 부족으로 추세를 확정 못 하면 `on_insufficient` 정책으로
    명시 결정(기본 "hold" = 유지, "cash" = 현금 이탈).

이 오버레이는 *후보*다. 옛 데이터 백테스트로는 "메커니즘이 폭락에서 현금으로 빠지는가"만
검증하고(엣지 주장 금지 — stale), "지금 통하는가"의 판정은 forward 페이퍼 트랙 + 스펙 035
엣지 판정이 한다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# 추세 판정 방식.
METHOD_SMA = "sma"  # 마지막 종가 > 최근 lookback 종가 단순이동평균
METHOD_ABSOLUTE_MOMENTUM = "absolute_momentum"  # lookback 기간 후행수익률 > 0
VALID_METHODS = (METHOD_SMA, METHOD_ABSOLUTE_MOMENTUM)

# 데이터 부족 시 정책.
ON_INSUFFICIENT_HOLD = "hold"  # 추세 확정 불가 → 가중치 유지(보유)
ON_INSUFFICIENT_CASH = "cash"  # 추세 확정 불가 → 현금 이탈(보수적 방어)
VALID_ON_INSUFFICIENT = (ON_INSUFFICIENT_HOLD, ON_INSUFFICIENT_CASH)


@dataclass(frozen=True)
class TrendSpec:
    """추세 필터 파라미터 — config 와 분리해 strategy 안에 둔다(결합도 최소)."""

    method: str = METHOD_SMA
    lookback: int = 200
    on_insufficient: str = ON_INSUFFICIENT_HOLD

    def __post_init__(self) -> None:
        if self.method not in VALID_METHODS:
            raise ValueError(f"unknown trend method: {self.method!r}")
        if self.lookback < 2:
            raise ValueError(f"trend lookback must be >= 2, got {self.lookback}")
        if self.on_insufficient not in VALID_ON_INSUFFICIENT:
            raise ValueError(
                f"unknown on_insufficient: {self.on_insufficient!r}"
            )


def above_trend(closes: Sequence[Decimal], spec: TrendSpec) -> bool | None:
    """종가 시계열(오름차순)이 추세 위에 있는가. 데이터 부족이면 None (fail-safe).

    - sma: 마지막 종가 > 최근 lookback 종가 단순이동평균. lookback 개 미만이면 None.
    - absolute_momentum: 마지막 종가 / lookback 전 종가 − 1 > 0. lookback+1 개 미만이면 None.
    """
    n = len(closes)
    if spec.method == METHOD_SMA:
        if n < spec.lookback:
            return None
        window = closes[-spec.lookback :]
        avg = sum(window, Decimal("0")) / Decimal(len(window))
        return closes[-1] > avg
    # absolute_momentum
    if n < spec.lookback + 1:
        return None
    past = closes[-1 - spec.lookback]
    if past <= 0:
        return None
    return (closes[-1] / past - Decimal("1")) > 0


def _ordered_closes(by_date: Mapping[date, Decimal]) -> list[Decimal]:
    """{날짜: 종가} → 날짜 오름차순 종가 리스트."""
    return [by_date[d] for d in sorted(by_date)]


@dataclass(frozen=True)
class TrendDecision:
    """한 종목의 추세 판정 — 진단/감사용."""

    symbol: str
    state: str  # "above" | "below" | "insufficient"
    kept: bool  # 가중치를 유지했는가(True) 현금으로 뺐는가(False)


def apply_trend_filter(
    weights: Mapping[str, Decimal],
    closes_by_symbol: Mapping[str, Mapping[date, Decimal]],
    spec: TrendSpec,
) -> tuple[dict[str, Decimal], list[TrendDecision]]:
    """추세 아래(또는 정책상 부족) 종목의 가중치를 0으로(현금) 만든다.

    재정규화하지 않는다 — 합이 1 미만이면 나머지는 현금(방어). 반환은 (필터된 가중치,
    종목별 판정 목록). 입력 weights 의 키 순서를 보존한다(결정론).
    """
    filtered: dict[str, Decimal] = {}
    decisions: list[TrendDecision] = []
    for symbol, w in weights.items():
        closes = _ordered_closes(closes_by_symbol.get(symbol, {}))
        verdict = above_trend(closes, spec)
        if verdict is True:
            filtered[symbol] = w
            decisions.append(TrendDecision(symbol, "above", True))
        elif verdict is False:
            decisions.append(TrendDecision(symbol, "below", False))
        else:  # None — 데이터 부족
            if spec.on_insufficient == ON_INSUFFICIENT_HOLD:
                filtered[symbol] = w
                decisions.append(TrendDecision(symbol, "insufficient", True))
            else:
                decisions.append(TrendDecision(symbol, "insufficient", False))
    return filtered, decisions


__all__ = [
    "METHOD_ABSOLUTE_MOMENTUM",
    "METHOD_SMA",
    "ON_INSUFFICIENT_CASH",
    "ON_INSUFFICIENT_HOLD",
    "TrendDecision",
    "TrendSpec",
    "above_trend",
    "apply_trend_filter",
]
