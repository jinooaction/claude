"""Spec 002 backtest run configuration models (FR-B-001).

`BacktestConfig` is the canonical TOML shape per
`specs/002-data-and-backtest/contracts/backtest-config.md`. Every
backtest run — flag-launched or config-launched — materialises one of
these and writes it to `data/backtests/<run_id>/inputs/run.toml` so
the run is reproducible from its own directory.

Decimal fields are quoted strings on the wire; float literals are
rejected at parse time to prevent binary precision drift.
"""

from __future__ import annotations

import tomllib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _coerce_decimal(value: object, field_name: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        raise TypeError(
            f"{field_name} must be a quoted string-decimal in TOML, not a float literal"
        )
    raise TypeError(f"unsupported type for {field_name}: {type(value)!r}")


def _coerce_utc(value: object, field_name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(f"{field_name} must be timezone-aware UTC")
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            raise ValueError(f"{field_name} must be timezone-aware UTC")
        return dt.astimezone(timezone.utc)
    raise TypeError(f"unsupported type for {field_name}: {type(value)!r}")


class CostModelOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    commission_bps: Decimal | None = None
    commission_min_usd: Decimal | None = None
    half_spread_bps: Decimal | None = None
    impact_coeff: Decimal | None = None
    participation_cap_pct: Decimal | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _no_floats(cls, value: object) -> object:
        if value is None:
            return None
        return _coerce_decimal(value, "cost_model override")


class CostModel(BaseModel):
    """Backtest cost model (R-2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commission_bps: Decimal = Decimal("0")
    commission_min_usd: Decimal = Decimal("0")
    half_spread_bps: Decimal = Decimal("5")
    impact_coeff: Decimal = Decimal("0.1")
    participation_cap_pct: Decimal = Decimal("10")
    per_symbol_overrides: Mapping[str, CostModelOverrides] = Field(default_factory=dict)

    @field_validator(
        "commission_bps",
        "commission_min_usd",
        "half_spread_bps",
        "impact_coeff",
        "participation_cap_pct",
        mode="before",
    )
    @classmethod
    def _coerce_dec(cls, value: object) -> Decimal:
        return _coerce_decimal(value, "cost_model field")

    @model_validator(mode="after")
    def _check_non_negative(self) -> "CostModel":
        for name in (
            "commission_bps",
            "commission_min_usd",
            "half_spread_bps",
            "impact_coeff",
            "participation_cap_pct",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"cost_model.{name} must be >= 0")
        if self.participation_cap_pct > 100:
            raise ValueError("cost_model.participation_cap_pct must be <= 100")
        return self

    def for_symbol(self, symbol: str) -> "CostModel":
        """Return a CostModel with per-symbol overrides folded in."""
        ov = self.per_symbol_overrides.get(symbol)
        if ov is None:
            return self
        merged = self.model_dump()
        merged.pop("per_symbol_overrides", None)
        for fld in (
            "commission_bps",
            "commission_min_usd",
            "half_spread_bps",
            "impact_coeff",
            "participation_cap_pct",
        ):
            v = getattr(ov, fld)
            if v is not None:
                merged[fld] = v
        merged["per_symbol_overrides"] = {}
        return CostModel.model_validate(merged)


class WalkForwardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    train_window_days: int = Field(gt=0)
    test_window_days: int = Field(gt=0)
    step_days: int = Field(gt=0)
    min_folds: int = Field(default=1, ge=1)


class OOSWindowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_utc: datetime
    to_utc: datetime
    enforced_at_read_layer: bool = True

    @field_validator("from_utc", "to_utc", mode="before")
    @classmethod
    def _utc(cls, value: object) -> datetime:
        return _coerce_utc(value, "oos.from_utc/to_utc")

    @model_validator(mode="after")
    def _check_order(self) -> "OOSWindowConfig":
        if self.from_utc >= self.to_utc:
            raise ValueError("oos.from_utc must be < oos.to_utc")
        if not self.enforced_at_read_layer:
            raise ValueError("OOSWindowConfig.enforced_at_read_layer must remain True")
        return self


class InstrumentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asset_class: str
    venue: str
    symbol: str
    vendor: str | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _upper(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("symbol must be a string")
        return value.upper()


class WindowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    from_utc: datetime
    to_utc: datetime
    as_of_ts_pin_utc: datetime

    @field_validator("from_utc", "to_utc", "as_of_ts_pin_utc", mode="before")
    @classmethod
    def _utc(cls, value: object) -> datetime:
        return _coerce_utc(value, "window timestamp")

    @model_validator(mode="after")
    def _check_order(self) -> "WindowConfig":
        if self.from_utc >= self.to_utc:
            raise ValueError("window.from_utc must be < window.to_utc")
        if self.as_of_ts_pin_utc < self.to_utc:
            raise ValueError(
                "window.as_of_ts_pin_utc must be >= window.to_utc"
                " (otherwise the run cannot read its own data)"
            )
        return self


class RuleRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str | None = None
    module: str | None = None
    snapshot_hash: str

    @model_validator(mode="after")
    def _exactly_one(self) -> "RuleRef":
        if (self.path is None) == (self.module is None):
            raise ValueError("[rule] must declare exactly one of `path` or `module`")
        return self


class ModeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["single", "walkforward", "oos"]
    walkforward: WalkForwardConfig | None = None
    oos: OOSWindowConfig | None = None

    @model_validator(mode="after")
    def _check_pairing(self) -> "ModeConfig":
        if self.kind == "single":
            if self.walkforward is not None or self.oos is not None:
                raise ValueError("mode.kind='single' must not declare walkforward or oos blocks")
        elif self.kind == "walkforward":
            if self.walkforward is None:
                raise ValueError("mode.kind='walkforward' requires [mode.walkforward]")
            if self.oos is not None:
                raise ValueError("mode.kind='walkforward' must not also declare [mode.oos]")
        elif self.kind == "oos":
            if self.oos is None:
                raise ValueError("mode.kind='oos' requires [mode.oos]")
            if self.walkforward is not None:
                raise ValueError("mode.kind='oos' must not also declare [mode.walkforward]")
        return self


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    seed: int = 0
    max_runtime_seconds: int = Field(default=600, gt=0)


class BacktestConfig(BaseModel):
    """The canonical run config (FR-B-001)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "002.1"
    rule: RuleRef
    window: WindowConfig
    instruments: tuple[InstrumentConfig, ...]
    mode: ModeConfig
    cost_model: CostModel = Field(default_factory=CostModel)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    @field_validator("instruments", mode="before")
    @classmethod
    def _coerce_instruments(cls, value: object) -> tuple:
        if value is None:
            raise ValueError("at least one [[instruments]] entry is required")
        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                raise ValueError("at least one [[instruments]] entry is required")
            return tuple(value)
        raise TypeError("instruments must be a list of tables")

    @model_validator(mode="after")
    def _check_oos_inside_window(self) -> "BacktestConfig":
        if self.mode.kind == "oos" and self.mode.oos is not None:
            if self.mode.oos.from_utc < self.window.from_utc:
                raise ValueError("mode.oos.from_utc must be >= window.from_utc")
            if self.mode.oos.to_utc > self.window.to_utc:
                raise ValueError("mode.oos.to_utc must be <= window.to_utc")
        return self


def load_backtest_config(path: str | Path) -> BacktestConfig:
    """Load and validate a `run.toml` against the canonical schema."""
    p = Path(path)
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    return BacktestConfig.model_validate(raw)
