"""SizingCaps — operator-declared risk-sizing limits.

Constitution principle I requires three caps to exist on every order:
per-trade, per-symbol, and global. This module models them as a frozen
pydantic value with cross-field invariants enforced at validation
time so a misconfigured caps section cannot reach the worker loop.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SizingCaps(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    per_trade_pct: Decimal = Field(..., gt=0, le=100)
    per_symbol_pct: Decimal = Field(..., gt=0, le=100)
    global_exposure_pct: Decimal = Field(..., gt=0, le=100)
    canary_capital_pct: Decimal = Field(..., gt=0, le=100)
    canary_min_duration_days: int = Field(..., ge=1)
    canary_acceptance_drawdown_pct: Decimal = Field(..., gt=0, le=100)

    @model_validator(mode="after")
    def _check_cross_field_invariants(self) -> SizingCaps:
        if not (self.per_trade_pct <= self.per_symbol_pct <= self.global_exposure_pct):
            raise ValueError(
                "caps must satisfy per_trade_pct <= per_symbol_pct <= global_exposure_pct; "
                f"got per_trade_pct={self.per_trade_pct}, "
                f"per_symbol_pct={self.per_symbol_pct}, "
                f"global_exposure_pct={self.global_exposure_pct}"
            )
        if self.canary_capital_pct > self.per_symbol_pct:
            raise ValueError(
                "caps.canary_capital_pct must not exceed caps.per_symbol_pct; "
                f"got canary_capital_pct={self.canary_capital_pct}, "
                f"per_symbol_pct={self.per_symbol_pct}"
            )
        return self
