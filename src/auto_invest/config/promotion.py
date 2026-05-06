"""Spec 002 promotion-threshold configuration (R-4 defaults).

Loaded from `config/promotion.toml` via the same `tomllib` + Pydantic
v2 plumbing as spec 001. If the file is missing, the defaults below
apply; this is the conservative baseline from research R-4.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class PromotionThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "002.1"

    min_oos_sharpe: Decimal = Decimal("1.0")
    max_oos_drawdown_pct: Decimal = Decimal("15")
    min_oos_trade_count: int = Field(default=30, gt=0)
    min_oos_window_days: int = Field(default=90, gt=0)

    max_live_vs_backtest_drawdown_divergence_pct: Decimal = Decimal("5")
    divergence_alert_window_days: int = Field(default=5, gt=0)

    @field_validator(
        "min_oos_sharpe",
        "max_oos_drawdown_pct",
        "max_live_vs_backtest_drawdown_divergence_pct",
        mode="before",
    )
    @classmethod
    def _coerce_dec(cls, value: object) -> Decimal:
        return _coerce_decimal(value, "promotion threshold")


def load_promotion_thresholds(path: str | Path | None) -> PromotionThresholds:
    """Load `config/promotion.toml`; missing file returns defaults."""
    if path is None:
        return PromotionThresholds()
    p = Path(path)
    if not p.exists():
        return PromotionThresholds()
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    return PromotionThresholds.model_validate(raw)
