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
    mode: Literal["fixed", "target_vol", "inverse_vol", "erc"] = "fixed"
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
            raise ValueError(
                "sizing.mode='inverse_vol' requires sizing_group to be set"
            )
        return self
