"""Backtest engine input config and window discriminated union.

`BacktestConfig` is the single input dataclass passed to `run_backtest`.
The CLI wrapper (T045) converts flags to this object; the spec 007
canary harness will construct it directly.

The two-arm `BacktestWindow` discriminated union lets the engine accept
either a contiguous date range OR a curated named dataset (e.g.
`synthetic_shock_v1`) without overloading.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from auto_invest.backtest.verdict import VerdictThresholds


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Window(_FrozenModel):
    """Contiguous inclusive `[start, end]` date range."""

    kind: Literal["window"] = "window"
    start: date
    end: date

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v: date, info):  # type: ignore[no-untyped-def]
        start = info.data.get("start")
        if start is not None and v < start:
            raise ValueError(f"window end {v} precedes start {start}")
        return v


class NamedDataset(_FrozenModel):
    """Reference to a curated frozen dataset under data/ohlcv/datasets/."""

    kind: Literal["named_dataset"] = "named_dataset"
    name: str

    @field_validator("name")
    @classmethod
    def _name_lower_snake(cls, v: str) -> str:
        if not v or v != v.lower() or " " in v or "-" in v:
            raise ValueError(f"named-dataset name must be lower_snake_case: {v!r}")
        return v


BacktestWindow = Window | NamedDataset


class BacktestConfig(_FrozenModel):
    """Single input dataclass for `run_backtest`."""

    rule_set_path: Path
    vendor: Literal["yfinance", "kis_historical"]
    window: BacktestWindow = Field(discriminator="kind")
    symbols: frozenset[str] | None = None
    seed: int = 0
    opening_cash_usd: Decimal = Decimal("100000.00")
    slippage_bps_market: int = 5
    risk_free_rate_annual: Decimal = Decimal("0")
    warmup_bars: int = 50
    verdict_thresholds: VerdictThresholds = VerdictThresholds()
    output_root: Path = Path("data/backtests")
    allow_dirty: bool = False

    @field_validator("symbols")
    @classmethod
    def _symbols_uppercased(cls, v: frozenset[str] | None) -> frozenset[str] | None:
        if v is None:
            return None
        return frozenset(s.upper() for s in v)

    @field_validator("slippage_bps_market")
    @classmethod
    def _slippage_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("slippage_bps_market must be >= 0")
        return v

    @field_validator("warmup_bars")
    @classmethod
    def _warmup_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("warmup_bars must be >= 1")
        return v
