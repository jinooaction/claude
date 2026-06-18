"""Autonomy authority levels.

The autonomy model is executable policy, not documentation. Markdown may be
generated from this module, but this module is the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AutonomyLevel(StrEnum):
    """Authority tiers for autonomous system actions."""

    READ_ONLY = "A0"
    SIMULATION = "A1"
    PROPOSAL = "A2"
    BOUNDED_LIVE = "A3"
    CAPITAL_SCALING = "A4"
    STRATEGY_REASSIGNMENT = "A5"
    SAFETY_BOUNDARY_CHANGE = "A6"

    @property
    def rank(self) -> int:
        return int(self.value[1:])


@dataclass(frozen=True)
class AutonomyPolicy:
    level: AutonomyLevel
    label: str
    description: str
    autonomous_allowed: bool
    operator_approval_required: bool


LEVEL_POLICIES: dict[AutonomyLevel, AutonomyPolicy] = {
    AutonomyLevel.READ_ONLY: AutonomyPolicy(
        level=AutonomyLevel.READ_ONLY,
        label="read-only",
        description="Inspect, report, diagnose, or render already-recorded state.",
        autonomous_allowed=True,
        operator_approval_required=False,
    ),
    AutonomyLevel.SIMULATION: AutonomyPolicy(
        level=AutonomyLevel.SIMULATION,
        label="simulation",
        description=(
            "Run backtests, paper trading, forward validation, and probes without live orders."
        ),
        autonomous_allowed=True,
        operator_approval_required=False,
    ),
    AutonomyLevel.PROPOSAL: AutonomyPolicy(
        level=AutonomyLevel.PROPOSAL,
        label="proposal",
        description="Create or record candidates, diagnostics, snapshots, or recommendations.",
        autonomous_allowed=True,
        operator_approval_required=False,
    ),
    AutonomyLevel.BOUNDED_LIVE: AutonomyPolicy(
        level=AutonomyLevel.BOUNDED_LIVE,
        label="bounded-live",
        description=(
            "Operate live within predeclared caps, whitelist, halt, audit, "
            "and reconciliation gates."
        ),
        autonomous_allowed=True,
        operator_approval_required=False,
    ),
    AutonomyLevel.CAPITAL_SCALING: AutonomyPolicy(
        level=AutonomyLevel.CAPITAL_SCALING,
        label="capital-scaling",
        description="Promote, demote, or arm capital under the measured capital ladder policy.",
        autonomous_allowed=True,
        operator_approval_required=False,
    ),
    AutonomyLevel.STRATEGY_REASSIGNMENT: AutonomyPolicy(
        level=AutonomyLevel.STRATEGY_REASSIGNMENT,
        label="strategy-reassignment",
        description="Select a validated challenger strategy under the reassignment gate policy.",
        autonomous_allowed=True,
        operator_approval_required=False,
    ),
    AutonomyLevel.SAFETY_BOUNDARY_CHANGE: AutonomyPolicy(
        level=AutonomyLevel.SAFETY_BOUNDARY_CHANGE,
        label="safety-boundary-change",
        description=(
            "Change caps, whitelist, loss budget, live authority, or other safety perimeter rules."
        ),
        autonomous_allowed=False,
        operator_approval_required=True,
    ),
}


def policy_for(level: AutonomyLevel) -> AutonomyPolicy:
    return LEVEL_POLICIES[level]
