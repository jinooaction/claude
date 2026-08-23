"""TradingRule, Trigger, Action — the operator's rule-language data model.

A rule answers the question: "when X happens, do Y for symbol Z up to
size W?" The trigger discriminator (`kind`) selects between the three
families v1 supports — time, price-threshold, indicator — per OD-1.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from auto_invest.config.enums import OrderType, Side, StrategyStage

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
TIMEFRAME_PATTERN = re.compile(r"^\d+[mhd]$")  # 1m, 5m, 1h, 1d, etc.
PRICE_DIRECTIONS: tuple[str, ...] = ("<=", ">=")


class TimeTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["time"] = "time"
    at_time: str
    weekdays: tuple[int, ...] | None = None  # 0=Mon..6=Sun; None means every day
    cooldown_seconds: int = Field(..., ge=0)

    @field_validator("at_time")
    @classmethod
    def _check_time_format(cls, v: str) -> str:
        if not TIME_PATTERN.match(v):
            raise ValueError(f"at_time must be HH:MM (24h), got {v!r}")
        return v

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, v: tuple[int, ...] | None) -> tuple[int, ...] | None:
        if v is None:
            return v
        for d in v:
            if not 0 <= d <= 6:
                raise ValueError(f"weekday must be 0-6 (0=Mon), got {d}")
        return v


class PriceTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["price"] = "price"
    direction: Literal["<=", ">="]
    threshold: Decimal = Field(..., gt=0)
    cooldown_seconds: int = Field(..., ge=0)


class IndicatorTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["indicator"] = "indicator"
    indicator: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    timeframe: str
    cooldown_seconds: int = Field(..., ge=0)

    @field_validator("timeframe")
    @classmethod
    def _check_timeframe(cls, v: str) -> str:
        if not TIMEFRAME_PATTERN.match(v):
            raise ValueError(f"timeframe must match pattern <int><m|h|d>, got {v!r}")
        return v


Trigger = Annotated[
    TimeTrigger | PriceTrigger | IndicatorTrigger,
    Field(discriminator="kind"),
]


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    side: Side
    order_type: OrderType
    qty: int = Field(..., gt=0)
    limit_price: str = Field(..., min_length=1)
    # `limit_price` is parsed by execution/order_router.py at runtime.
    # It may be a Decimal-like literal ("180.00") or a formula
    # ("trigger - 0.10", "last_close * 1.001"). The grammar is part of
    # the order_router contract, not this model.


class JudgmentConfig(BaseModel):
    """Spec 004 — 판단 지점 자문을 이 룰이 어떻게 결정론적으로 소비하는지 선언.

    `enabled=False`(기본)면 판단 지점 비활성 — 룰은 v1 동작. 안전 불변량:
    `size_down_factor` 는 0..1 로 제약되어 자문은 노출을 **늘릴 수 없다**(줄이거나
    건너뛰기만). `block_*` 는 news_screen 소비 노브다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = False
    halt_min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    size_down_factor: float = Field(default=0.5, ge=0.0, le=1.0)
    volatility_threshold: float = Field(default=0.0, ge=0.0)
    block_buy_stance: Literal["bear"] | None = "bear"
    block_min_confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class SizingConfig(BaseModel):
    """Spec 017 — 변동성 기반 포지션 사이징 설정(선택). 비커널.

    `mode="fixed"`(기본)면 v1 고정 수량 동작과 byte 동일. `mode="target_vol"`이면
    실현 변동성이 `target_volatility_pct`(분수가 아니라 퍼센트)와 비교돼 룰의 기준 수량을
    조절한다.

    - 슬라이스 1(하향 전용): 실현 변동성이 타깃을 초과하면 수량을 **줄인다**. `max_scale`
      기본값 1이라 절대 늘리지 않는다.
    - 슬라이스 2(양방향): `max_scale > 1`로 설정하면 잔잔한 구간(실현 < 타깃)에서 수량을
      타깃 리스크 예산까지 **늘린다**(진짜 변동성 타깃팅). 확대는 `max_scale` 배수로
      제한되고, 그 위에서도 K1 캡 게이트가 변형 없이 실행돼 초과분을 거부한다.
    - 슬라이스 2b(`mode="inverse_vol"`): 같은 `sizing_group`(아래 `TradingRule.sizing_group`)
      에 속한 룰들의 실현 변동성을 재서, 변동성 가장 낮은 멤버를 기준(가중치 1)으로 높은
      변동성 멤버를 줄여 **리스크 기여도를 균형화**한다(역변동성 = 리스크 패리티). 항상
      하향 전용(가중치 ≤ 1)이라 기준 수량 위로 노출을 올리지 않는다.
    - 슬라이스 3(`correlation_haircut > 0`, inverse_vol 그룹에서만): 그룹 멤버 간 수익률
      상관이 높으면(분산 안 됨) 가중치를 `1 - strength × 평균상관`만큼 더 줄인다(상관 ≤ 0
      이면 헤어컷 없음). 상관 높은(집중된) 베팅을 줄이는 보수적 하향 전용 통제다. 기본 0.

    어느 경우든 사이저는 K1 캡 게이트 **전에** 수량을 제안만 한다 — K1이 그대로
    상한으로 바인딩하므로 사이저는 노출을 안전 경계 위로 절대 올릴 수 없다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["fixed", "target_vol", "inverse_vol", "erc", "min_variance", "max_sharpe"] = (
        "fixed"
    )
    target_volatility_pct: Decimal = Field(default=Decimal("2.0"), gt=0)
    lookback_bars: int = Field(default=20, ge=2)
    min_scale: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    # 상향 한도(슬라이스 2). 기본 1 = 하향 전용(슬라이스 1과 byte 동일). > 1이면 잔잔한
    # 구간에서 확대 허용. K1 캡이 진짜 천장이므로 이 값은 fat-finger 방지용 sanity 한도다.
    max_scale: Decimal = Field(default=Decimal("1"), ge=1, le=10)
    # 상관 헤어컷 강도(슬라이스 3, inverse_vol 그룹에서만). 0 = 끔(슬라이스 2b byte 동일).
    # > 0이면 그룹 멤버 간 양의 상관에 비례해 가중치를 추가로 줄인다(하향 전용).
    correlation_haircut: Decimal = Field(default=Decimal("0"), ge=0, le=1)


class RankingFilter(BaseModel):
    """스펙 021 — 횡단면 모멘텀 순위 필터. 비커널.

    `universe` 전체 심볼을 `period`-바 수익률로 내림차순 순위 매겨,
    현재 룰의 심볼이 상위 `top_n`개 또는 상위 `top_pct`% 이내일 때만
    주문을 통과시킨다. 통과 못하면 `SKIPPED_BY_RANKING` 반환(하향 전용, K1 불변).

    `top_n`과 `top_pct` 중 정확히 하나만 설정 가능.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    universe: tuple[str, ...] = Field(..., min_length=2)
    period: int = Field(..., ge=1)
    top_n: int | None = Field(default=None, ge=1)
    top_pct: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def _require_exactly_one(self) -> RankingFilter:
        if (self.top_n is None) == (self.top_pct is None):
            raise ValueError("RankingFilter: set exactly one of top_n or top_pct")
        return self

    def qualifies(self, symbol: str, ranked: list[tuple[str, Decimal]]) -> bool:
        """True if *symbol* passes this filter given a pre-computed ranked list."""
        if self.top_n is not None:
            cutoff = min(self.top_n, len(ranked))
        else:
            cutoff = max(1, math.ceil(len(ranked) * (self.top_pct or 0) / 100))
        top_symbols = {s for s, _ in ranked[:cutoff]}
        return symbol in top_symbols


_MIN_QUALITY_BARS = 30


class QualityFilter(BaseModel):
    """스펙 023 — 가격 기반 퀄리티 팩터 필터. 비커널.

    유니버스 심볼을 ``lookback_bars`` 기간 퀄리티 점수(롤링 샤프 / (1 + |최대 드로다운|))로
    내림차순 순위 매겨, 현재 룰의 심볼이 상위 `top_n`개 또는 상위 `top_pct`% 이내일 때만
    주문을 통과시킨다. 통과 못하면 `SKIPPED_BY_QUALITY` 반환(하향 전용, K1 불변).

    `top_n`과 `top_pct` 중 정확히 하나만 설정 가능.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    universe: tuple[str, ...] = Field(..., min_length=2)
    lookback_bars: int = Field(default=60, ge=_MIN_QUALITY_BARS)
    top_n: int | None = Field(default=None, ge=1)
    top_pct: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def _require_exactly_one(self) -> QualityFilter:
        if (self.top_n is None) == (self.top_pct is None):
            raise ValueError("QualityFilter: set exactly one of top_n or top_pct")
        return self

    def qualifies(self, symbol: str, ranked: list[tuple[str, Decimal]]) -> bool:
        """True if *symbol* passes this filter given a pre-computed ranked list."""
        if self.top_n is not None:
            cutoff = min(self.top_n, len(ranked))
        else:
            cutoff = max(1, math.ceil(len(ranked) * (self.top_pct or 0) / 100))
        top_symbols = {s for s, _ in ranked[:cutoff]}
        return symbol in top_symbols


# 스펙 025: 합성 알파 점수에 허용되는 팩터 이름. `strategy/factors.py`의
# `KNOWN_FACTORS`와 반드시 일치해야 한다(여기서 그 모듈을 임포트하면
# config.rules -> strategy.factors -> strategy.sizing -> config.rules 순환이
# 생기므로 리터럴로 둔다; test_spec_025_composite_factor.py가 동기화를 검증).
KNOWN_COMPOSITE_FACTORS: tuple[str, ...] = (
    "momentum",
    "momentum_gap",
    "short_reversal",
    "quality",
    "low_volatility",
    "mean_reversion",
)


class CompositeFactorFilter(BaseModel):
    """스펙 025 — 다요인 합성 알파 점수 필터. 비커널.

    유니버스 전체를 여러 팩터(모멘텀·퀄리티·저변동성·평균회귀)의 **횡단면 z-점수
    가중합**(하나의 합성 점수)으로 내림차순 순위 매겨, 현재 룰의 심볼이 상위 `top_n`개
    또는 상위 `top_pct`% 이내일 때만 주문을 통과시킨다. 통과 못하면
    `SKIPPED_BY_COMPOSITE` 반환(하향 전용, K1 불변).

    스펙 021(모멘텀 단일)·023(퀄리티 단일) 필터를 일반화한다 — 단일 팩터로 순차
    필터링하는 대신 여러 팩터를 하나의 점수로 결합해 "여러 면에서 두루 좋은" 종목을
    "한 면에서만 극단적인" 종목보다 선호한다.

    `weights` 키는 `KNOWN_COMPOSITE_FACTORS` 부분집합이어야 하고 최소 하나는 0이
    아니어야 한다. `top_n`과 `top_pct` 중 정확히 하나만 설정 가능.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    universe: tuple[str, ...] = Field(..., min_length=2)
    weights: dict[str, Decimal] = Field(..., min_length=1)
    lookback_bars: int = Field(default=60, ge=30)
    momentum_period: int = Field(default=20, ge=1)
    bb_period: int = Field(default=20, ge=2)
    bb_std: float = Field(default=2.0, gt=0)
    top_n: int | None = Field(default=None, ge=1)
    top_pct: float | None = Field(default=None, gt=0, le=100)

    @field_validator("weights")
    @classmethod
    def _check_weights(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        unknown = set(v) - set(KNOWN_COMPOSITE_FACTORS)
        if unknown:
            raise ValueError(
                f"unknown composite factor(s): {sorted(unknown)}; "
                f"allowed: {list(KNOWN_COMPOSITE_FACTORS)}"
            )
        if all(w == 0 for w in v.values()):
            raise ValueError("CompositeFactorFilter: at least one factor weight must be non-zero")
        return v

    @model_validator(mode="after")
    def _require_exactly_one(self) -> CompositeFactorFilter:
        if (self.top_n is None) == (self.top_pct is None):
            raise ValueError("CompositeFactorFilter: set exactly one of top_n or top_pct")
        return self

    def qualifies(self, symbol: str, ranked: list[tuple[str, Decimal]]) -> bool:
        """True if *symbol* passes this filter given a pre-computed ranked list."""
        if self.top_n is not None:
            cutoff = min(self.top_n, len(ranked))
        else:
            cutoff = max(1, math.ceil(len(ranked) * (self.top_pct or 0) / 100))
        top_symbols = {s for s, _ in ranked[:cutoff]}
        return symbol in top_symbols


# 스펙 032: 재조정 목표 비중 산정 방식. equal/score_proportional 는 rebalance 자체
# 계산, 나머지는 strategy/sizing.py 의 포트폴리오 최적화기를 재사용한다.
KNOWN_WEIGHT_SCHEMES: tuple[str, ...] = (
    "equal",
    "score_proportional",
    "inverse_vol",
    "min_variance",
    "max_sharpe",
    "erc",
)


class TrendFilterConfig(BaseModel):
    """스펙 036 — 절대 모멘텀 추세 필터(드로다운 방어 오버레이) 설정. 비커널·옵트인.

    `[portfolio.trend_filter]` 로 켜면 목표 가중치 산출 마지막에 종목별 추세 게이트가
    적용된다 — 자기 추세 아래로 내려간 종목은 가중치 0(현금)으로 빠진다. 재정규화하지
    않으므로 합이 1 미만이 되고 그 차이는 현금 버퍼(방어)다. 설정을 생략하면(None)
    가중치는 손도 안 댄다(기존 동작 byte 동일).

    method: "sma"(마지막 종가 > lookback SMA) | "absolute_momentum"(lookback 후행수익률>min_return).
    lookback: 추세 판정 기간(일봉 수). 200 ≈ 약 10개월(고전 추세추종 기본).
    on_insufficient: 데이터 부족 시 "hold"(유지) | "cash"(보수적 현금 이탈).
    min_return_pct: absolute_momentum 의 기대수익 바닥(%). 후행수익률이 이 값보다 커야
      보유한다(아니면 현금). 0 = 자기 수익 양수여야 함(듀얼 모멘텀). 양수면 더 엄격
      (예: 무위험 위만). **상대 순위 1위라도 이 절대 바닥 미달이면 안 산다** — 후보가
      전부 나쁠 때 "그나마 1위"를 사는 결함을 막는다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    method: Literal["sma", "absolute_momentum"] = "sma"
    lookback: int = Field(default=200, ge=2)
    on_insufficient: Literal["hold", "cash"] = "hold"
    min_return_pct: Decimal = Field(default=Decimal("0"))
    # 스펙 048 — 다중 속도 앙상블(분수 노출). 설정하면 단일 lookback 이진 게이트 대신 이 여러
    # 속도(일봉 SMA 창) 다발의 *추세 위 비율*(0..1)만큼 노출하고 나머지는 현금이다 — 단일 속도의
    # 절벽(0↔1)을 부드럽게(샤프↑·낙폭↓, 스펙 048). 예: [63,126,189,252] ≈ 3/6/9/12개월. method
    # 는 SMA 고정(검증된 형태). on_insufficient 는 창별 적용. None 이면 기존 단일 속도(byte 동일).
    ensemble_windows: tuple[int, ...] | None = None

    @field_validator("ensemble_windows")
    @classmethod
    def _check_ensemble_windows(cls, v: tuple[int, ...] | None) -> tuple[int, ...] | None:
        if v is not None and (len(v) == 0 or any(w < 2 for w in v)):
            raise ValueError("ensemble_windows must be non-empty with each >= 2")
        return v


class MacroPolicyConfig(BaseModel):
    """Optional spec-151 macro overlay shared by research and execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    family: Literal[
        "curve_cycle", "inflation_direction", "labor_growth_shock", "vix_shock_recovery"
    ]
    base_portfolio: Literal["equal_3asset", "factory-relative_momentum-cb2e32f74390"]
    threshold: Decimal
    confirmation_days: int | None = Field(default=None, ge=1)
    release_threshold_pp: Decimal | None = Field(default=None, ge=0)
    direction_months: Literal[3, 6] | None = None
    cooldown_days: int | None = Field(default=None, ge=1)
    tilt_pct: Decimal = Field(..., gt=0, le=100)

    @model_validator(mode="after")
    def _family_fields(self) -> MacroPolicyConfig:
        if self.family == "curve_cycle":
            if self.confirmation_days is None or self.release_threshold_pp is None:
                raise ValueError("curve_cycle requires confirmation_days and release_threshold_pp")
        elif self.family in {"inflation_direction", "labor_growth_shock"}:
            if self.direction_months is None:
                raise ValueError(f"{self.family} requires direction_months")
        elif self.confirmation_days is None or self.cooldown_days is None:
            raise ValueError("vix_shock_recovery requires confirmation_days and cooldown_days")
        return self


class PortfolioRebalanceConfig(BaseModel):
    """스펙 032 — 횡단면 포트폴리오 재조정 설정. 비커널.

    유니버스 전체를 합성 알파 점수(스펙 025 `composite_scores`)로 매겨 상위 `top_n`개
    (또는 `top_pct`%)를 `weight_scheme` 으로 가중한 **목표 포트폴리오**를 만들고,
    `rebalance_every_n_sessions` 마다 현재 보유와의 차이를 매수+매도로 재조정한다.
    목표에 없는 보유 종목은 전량 매도(청산)된다 — 기존 룰 기반 매수 전용 시스템에
    빠져 있던 매도 차원이다.

    슬라이스 1 은 백테스트·CLI 전용(라이브 워커 무배선, byte 동일). 라이브 배선·실제
    재조정 주문은 후속 슬라이스이며 돈 움직이는 운용 변경이라 운영자 게이트다.

    플래너는 수량을 제안만 하고, 모든 매수는 라이브와 동일한 K1 캡 게이트 체인을
    통과한다 — 캡이 천장이라 노출을 안전 경계 위로 올릴 수 없다(하향 전용 안전망).

    `weights` 키는 `KNOWN_COMPOSITE_FACTORS` 부분집합이어야 하고 최소 하나는 0이
    아니어야 한다(CompositeFactorFilter 와 동일 규약). `top_n`·`top_pct` 정확히 하나.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(..., min_length=1)
    universe: tuple[str, ...] = Field(..., min_length=2)
    weight_scheme: Literal[
        "equal", "score_proportional", "inverse_vol", "min_variance", "max_sharpe", "erc"
    ] = "equal"
    # 스펙 032 — 재조정 동작 방식.
    #   "rebalance"(기본): 매 주기 목표 비중으로 되돌린다(승자도 덜어냄). 강세장에서
    #     승자 트리밍 + 높은 회전율로 단순 보유에 뒤질 수 있다(REAL-DATA-FINDINGS 참고).
    #   "hold_replace": 저회전 "승자 유지" — 순위에서 이탈한 보유만 매도(청산)하고, 새
    #     진입 종목만 매수한다. 기존 보유는 비중을 되돌리지 않고 그대로 둔다(승자가 계속
    #     달리게). 회전율이 크게 낮아져 비용을 아끼고 강세장 트리밍 손실을 없앤다.
    rebalance_mode: Literal["rebalance", "hold_replace"] = "rebalance"
    # 합성 점수 파라미터 (스펙 025 재사용)
    weights: dict[str, Decimal] = Field(..., min_length=1)
    lookback_bars: int = Field(default=60, ge=30)
    momentum_period: int = Field(default=20, ge=1)
    bb_period: int = Field(default=20, ge=2)
    bb_std: float = Field(default=2.0, gt=0)
    # 선택 폭
    top_n: int | None = Field(default=None, ge=1)
    top_pct: float | None = Field(default=None, gt=0, le=100)
    # 투자 비율(현금 버퍼 유지). 목표 금액 = 비중 × 자본 × invested_fraction.
    invested_fraction: Decimal = Field(default=Decimal("0.95"), gt=0, le=1)
    # 재조정 주기(거래 세션 수). 21 ≈ 월 1회(영업일 기준).
    rebalance_every_n_sessions: int = Field(default=21, ge=1)
    # 무거래 밴드: 목표 비중이 현재 비중에서 이 % 미만으로만 바뀌면 주문 안 함(회전율 통제).
    rebalance_threshold_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    # 최소 명목(USD). 이보다 작은 자투리 주문은 거른다(회전율·비용 통제).
    min_notional_usd: Decimal = Field(default=Decimal("0"), ge=0)
    # 스펙 036 — 절대 모멘텀 추세 필터(드로다운 방어). 생략 시 미적용(기존 동작 byte 동일).
    trend_filter: TrendFilterConfig | None = None
    macro_policy: MacroPolicyConfig | None = None

    @field_validator("universe")
    @classmethod
    def _normalize_universe(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(s.upper() for s in v)

    @field_validator("weights")
    @classmethod
    def _check_weights(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        unknown = set(v) - set(KNOWN_COMPOSITE_FACTORS)
        if unknown:
            raise ValueError(
                f"unknown composite factor(s): {sorted(unknown)}; "
                f"allowed: {list(KNOWN_COMPOSITE_FACTORS)}"
            )
        if all(w == 0 for w in v.values()):
            raise ValueError(
                "PortfolioRebalanceConfig: at least one factor weight must be non-zero"
            )
        return v

    @model_validator(mode="after")
    def _require_exactly_one(self) -> PortfolioRebalanceConfig:
        if (self.top_n is None) == (self.top_pct is None):
            raise ValueError("PortfolioRebalanceConfig: set exactly one of top_n or top_pct")
        return self


class OrderLifecycleConfig(BaseModel):
    """스펙 030 — 미체결 주문 수명 관리 설정(선택). 비커널.

    `TradingRule.lifecycle` 가 None(기본)이면 모든 경로가 byte 동일 — 기존 룰은 주문
    수명 관리를 전혀 받지 않는다(회귀 무손상). 각 필드는 독립 옵트인:

    - `ttl_seconds`: 미체결이 이 초를 넘기면 자동 취소(G1). None 이면 TTL 취소 안 함.
    - `requote_drift_pct`: 지정가가 현재 중간가에서 이 % 이상 벌어지면 취소-재호가(G2).
      None 이면 재호가 안 함. 재호가는 K1 캡 게이트 체인을 다시 통과한다(노출 상한 무변경).
    - `requote_after_seconds`: 재호가를 고려하기 전 최소 경과 시간(폭주 방지). 기본 30초.
    - `marketable_limit_bps`: 제출 시 시장가 가까운 공격적 지정가의 버퍼(basis point, G3).
      매수=ask 위 / 매도=bid 아래로 buffer_bps 만큼. None 이면 기존 limit_price 표현식 사용.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    ttl_seconds: int | None = Field(default=None, ge=1)
    requote_drift_pct: Decimal | None = Field(default=None, gt=0)
    requote_after_seconds: int = Field(default=30, ge=0)
    marketable_limit_bps: int | None = Field(default=None, ge=0)


class TradingRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(..., min_length=1)
    symbol: str
    stage: StrategyStage
    priority: int
    enabled: bool = True
    trigger: Trigger
    action: Action
    judgment: JudgmentConfig | None = None
    sizing: SizingConfig | None = None
    # 사이징 그룹 이름(슬라이스 2b). 같은 이름의 inverse_vol 룰끼리 역변동성 리스크
    # 패리티 배분을 공유한다. None이면 그룹 없음(기존 동작 byte 동일).
    sizing_group: str | None = None
    # 스펙 020: 레짐 감지용 인덱스 심볼(예: "SPY", "069500"). 값이 있으면
    # 해당 심볼의 봉으로 레짐을 판별해 주문 수량에 레짐 배율을 적용한다.
    # None이면 레짐 적용 안 함(기존 동작 byte 동일).
    regime_index_symbol: str | None = None
    # 레짐별 신호 배율 오버라이드. 없으면 DEFAULT_REGIME_SCALE 기본값 사용.
    # 예: {"trending": "1.0", "ranging": "0.5", "bear": "0.2"}
    regime_scale: dict[str, Decimal] | None = None
    # 스펙 021: 횡단면 모멘텀 순위 필터. None이면 필터 없음(기존 동작 byte 동일).
    ranking_filter: RankingFilter | None = None
    # 스펙 023: 가격 기반 퀄리티 필터. None이면 필터 없음(기존 동작 byte 동일).
    quality_filter: QualityFilter | None = None
    # 스펙 025: 다요인 합성 알파 점수 필터. None이면 필터 없음(기존 동작 byte 동일).
    composite_filter: CompositeFactorFilter | None = None
    # 스펙 030: 미체결 주문 수명 관리(TTL 취소·재호가·marketable-limit). None이면
    # 수명 관리 없음(기존 동작 byte 동일).
    lifecycle: OrderLifecycleConfig | None = None

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _require_group_for_inverse_vol(self) -> TradingRule:
        # inverse_vol 모드는 그룹 멤버끼리 변동성을 비교하므로 sizing_group 필수.
        if (
            self.sizing is not None
            and self.sizing.mode == "inverse_vol"
            and self.sizing_group is None
        ):
            raise ValueError("sizing.mode='inverse_vol' requires sizing_group to be set")
        return self
