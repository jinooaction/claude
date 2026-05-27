"""In-memory entity models for the backtest engine.

Mirrors `specs/008-backtest-engine/data-model.md § In-memory entities`.
Every Decimal is canonicalised to 6 dp via `canonicalise_decimal` so
the determinism contract (FR-B15) holds byte-for-byte across machines
and Python builds.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CANONICAL_QUANTUM = Decimal("0.000001")


def canonicalise_decimal(value: Decimal | str | int | float) -> str:
    """Return the canonical 6-decimal-place string form for byte-stability.

    Uses Decimal.quantize (ROUND_HALF_EVEN by default) — NOT f-string
    formatting, which can round differently across builds. See research.md
    R-B5 (determinism boundary).
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return str(value.quantize(CANONICAL_QUANTUM))


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class OHLCVBar(_Frozen):
    """One historical bar. See data-model.md § OHLCVBar."""

    symbol: str
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0)
    session_schedule_tag: Literal["regular", "early_close", "holiday", "halted"]

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError(f"price must be positive, got {v}")
        return v


class DataQualityWarning(_Frozen):
    symbol: str
    session_date: date | None = None
    kind: Literal[
        "zero_volume_regular",
        "gap_over_7_days",
        "delisted_after",
        "pre_listing",
        "schedule_tag_mismatch",
    ]
    note: str = ""


class RuleBacktestResult(_Frozen):
    """Per-rule outcome. See data-model.md § RuleBacktestResult."""

    rule_id: str
    symbol: str
    total_return_pct: Decimal
    max_drawdown_pct: Decimal = Field(ge=0)
    sharpe_ratio: Decimal
    order_count: int = Field(ge=0)
    fill_count: int = Field(ge=0)
    gate_rejection_count_by_gate: dict[str, int] = Field(default_factory=dict)
    notional_traded_usd: Decimal = Field(ge=0)
    commission_usd: Decimal = Field(default=Decimal("0"), ge=0)
    slippage_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    slippage_assumption: str = "zero"
    # spec 016 슬라이스 2 — 라이브 성과 엔진과 같은 거래 단위 잣대 (헌법 X.2 단일 잣대).
    # 청산(매도) 손익에서 backtest/metrics.py 공용 정의로 계산. 청산 0건이면 win_rate/
    # profit_factor 는 None(N/A), sortino 는 자산곡선 하방편차 기준(거래 없으면 0).
    closed_trades: int = Field(default=0, ge=0)
    win_rate: Decimal | None = None
    profit_factor: Decimal | None = None
    sortino_ratio: Decimal = Decimal("0")

    @field_validator("fill_count")
    @classmethod
    def _fill_le_order(cls, v: int, info) -> int:
        order_count = info.data.get("order_count")
        if order_count is not None and v > order_count:
            raise ValueError(f"fill_count {v} > order_count {order_count}")
        return v


class BacktestSummary(_Frozen):
    aggregate_return_pct: Decimal
    aggregate_max_drawdown_pct: Decimal
    aggregate_sharpe: Decimal
    per_rule: list[RuleBacktestResult] = Field(default_factory=list)
    total_orders: int = Field(ge=0)
    total_fills: int = Field(ge=0)
    total_gate_rejections: int = Field(ge=0)
    total_commission_usd: Decimal = Field(default=Decimal("0"), ge=0)
    total_slippage_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    data_quality_warnings: list[DataQualityWarning] = Field(default_factory=list)
    # spec 016 슬라이스 2 — 포트폴리오 거래 단위 잣대. aggregate_sortino 는 룰별
    # 동일가중 평균(aggregate_sharpe 규약과 동일), 승률·손익비는 전 룰의 청산을
    # 한데 모아(pooled) 계산한다(비율 평균보다 의미 있음). 청산 0건이면 None.
    aggregate_sortino: Decimal = Decimal("0")
    total_closed_trades: int = Field(default=0, ge=0)
    aggregate_win_rate: Decimal | None = None
    aggregate_profit_factor: Decimal | None = None


class BacktestRun(_Frozen):
    """Run header. See data-model.md § BacktestRun."""

    run_id: str
    invoker: Literal["cli", "canary"]
    ruleset_path: Path
    ruleset_sha256: str
    dataset_version: str
    date_start: date
    date_end: date
    replay_seed: int = 0
    fill_model: Literal["pessimistic_zero_slip"] = "pessimistic_zero_slip"
    cost_model: str = "zero"
    judgment_mode: Literal["stub"] = "stub"
    synthetic_shock: bool = False
    start_ts: datetime
    end_ts: datetime | None = None
    status: Literal["running", "completed", "failed"] = "running"
    summary: BacktestSummary | None = None


class SyntheticShockDay(_Frozen):
    """A named historical shock day. See data-model.md § SyntheticShockDay."""

    name: str
    session_date: date
    expected_gate_trip: str = ""
    note: str = ""


__all__ = [
    "CANONICAL_QUANTUM",
    "BacktestRun",
    "BacktestSummary",
    "DataQualityWarning",
    "OHLCVBar",
    "RuleBacktestResult",
    "SyntheticShockDay",
    "canonicalise_decimal",
]
