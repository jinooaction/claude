"""TradingRule, Trigger, Action — the operator's rule-language data model.

A rule answers the question: "when X happens, do Y for symbol Z up to
size W?" The trigger discriminator (`kind`) selects between the three
families v1 supports — time, price-threshold, indicator — per OD-1.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    실현 변동성이 `target_volatility_pct`(분수가 아니라 퍼센트)를 초과할 때 룰의 기준
    수량을 **줄인다**(슬라이스 1 하향 전용 — 스케일 ≤ 1). 사이저는 K1 캡 게이트 전에
    수량을 제안만 하며, K1이 그대로 상한으로 바인딩한다(절대 노출을 늘릴 수 없음).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["fixed", "target_vol"] = "fixed"
    target_volatility_pct: Decimal = Field(default=Decimal("2.0"), gt=0)
    lookback_bars: int = Field(default=20, ge=2)
    min_scale: Decimal = Field(default=Decimal("0"), ge=0, le=1)


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

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        return v.upper()
