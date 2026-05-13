"""Promotion verdict thresholds and verdict computation.

FR-B21 v1 baseline (frozen during /speckit-clarify Q4):
- total_return_pct >= 0
- max_drawdown_pct <= 10
- sharpe          >= 0.5

The verdict is advisory in v1; spec 007's hardened canary (when shipped)
is the binding gate per constitution IX.B-2. Reasons are emitted in a
deterministic order so two reruns with identical inputs produce
byte-identical reason lists (FR-B12).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class VerdictThresholds(BaseModel):
    """Frozen v1 baseline; operators MAY override per-run via input flags."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_return_pct_min: Decimal = Decimal("0")
    max_drawdown_pct_max: Decimal = Decimal("10")
    sharpe_min: Decimal = Decimal("0.5")


class Verdict(BaseModel):
    """Final advisory promotion verdict for a single backtest run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    promote_eligible: bool
    reasons: list[str]


def compute_verdict(
    *,
    total_return_pct: Decimal,
    max_drawdown_pct: Decimal,
    sharpe: Decimal | None,
    thresholds: VerdictThresholds,
) -> Verdict:
    """Apply the three thresholds in canonical order; return Verdict.

    `sharpe is None` means the run hit bankruptcy at some point (R-7);
    that case never promotes.
    """
    reasons: list[str] = []
    passing = True

    # 1. total return
    op_r = "≥" if total_return_pct >= thresholds.total_return_pct_min else "<"
    if op_r == "<":
        passing = False
    reasons.append(f"total_return_pct {total_return_pct} {op_r} {thresholds.total_return_pct_min}")

    # 2. max drawdown
    op_d = "≤" if max_drawdown_pct <= thresholds.max_drawdown_pct_max else ">"
    if op_d == ">":
        passing = False
    reasons.append(f"max_drawdown_pct {max_drawdown_pct} {op_d} {thresholds.max_drawdown_pct_max}")

    # 3. sharpe (None on bankruptcy)
    if sharpe is None:
        passing = False
        reasons.append("sharpe_annualised null (bankruptcy)")
    else:
        op_s = "≥" if sharpe >= thresholds.sharpe_min else "<"
        if op_s == "<":
            passing = False
        reasons.append(f"sharpe_annualised {sharpe} {op_s} {thresholds.sharpe_min}")

    return Verdict(promote_eligible=passing, reasons=reasons)
