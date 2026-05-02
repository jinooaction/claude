"""Canary auto-pause (FR-014, constitution VI).

Tracks rolling drawdown per rule and decides at session close whether
the strategy should be paused. The decision is consumed by the worker,
which writes the corresponding STRATEGY_PAUSED audit row when needed.

State is in-memory; pause status across worker restarts is recovered
from the audit log via `restore_pause_status`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from auto_invest.config.caps import SizingCaps

CanaryAction = Literal["CONTINUE", "PAUSE_NOW", "ALREADY_PAUSED"]


@dataclass
class CanaryRuntime:
    """Mutable in-memory canary state for one rule."""

    rule_id: str
    starting_value_usd: Decimal
    peak_value_usd: Decimal
    paused: bool = False


@dataclass(frozen=True)
class CanaryDecision:
    action: CanaryAction
    reason: str | None = None
    drawdown_pct: Decimal = Decimal("0")


def initial_state(rule_id: str, starting_value_usd: Decimal) -> CanaryRuntime:
    return CanaryRuntime(
        rule_id=rule_id,
        starting_value_usd=starting_value_usd,
        peak_value_usd=starting_value_usd,
    )


def evaluate_session_close(
    state: CanaryRuntime,
    *,
    current_value_usd: Decimal,
    caps: SizingCaps,
) -> CanaryDecision:
    """Update `state` in place and return the action for this session close.

    Policy:
      - Already paused -> ALREADY_PAUSED (no further state changes).
      - New high water mark -> peak updated; CONTINUE.
      - Drawdown <= acceptance -> CONTINUE.
      - Drawdown > acceptance -> set paused=True; PAUSE_NOW.
    """
    if state.paused:
        return CanaryDecision(action="ALREADY_PAUSED")

    if current_value_usd > state.peak_value_usd:
        state.peak_value_usd = current_value_usd
        return CanaryDecision(action="CONTINUE", drawdown_pct=Decimal("0"))

    if state.peak_value_usd == 0:
        return CanaryDecision(action="CONTINUE")

    drawdown_pct = (
        (state.peak_value_usd - current_value_usd) / state.peak_value_usd * Decimal(100)
    )
    if drawdown_pct > caps.canary_acceptance_drawdown_pct:
        state.paused = True
        return CanaryDecision(
            action="PAUSE_NOW",
            reason=(
                f"drawdown {drawdown_pct}% exceeds canary acceptance "
                f"{caps.canary_acceptance_drawdown_pct}%"
            ),
            drawdown_pct=drawdown_pct,
        )
    return CanaryDecision(action="CONTINUE", drawdown_pct=drawdown_pct)


def restore_pause_status(conn: sqlite3.Connection, rule_id: str) -> bool:
    """Return True if the rule's last lifecycle event in the audit log
    was STRATEGY_PAUSED (i.e., the worker restarted while paused)."""
    row = conn.execute(
        """
        SELECT event_type FROM audit_log
        WHERE rule_id = ?
          AND event_type IN ('STRATEGY_PAUSED', 'STRATEGY_PROMOTED')
        ORDER BY seq DESC
        LIMIT 1
        """,
        (rule_id,),
    ).fetchone()
    return row is not None and row["event_type"] == "STRATEGY_PAUSED"
