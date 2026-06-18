from __future__ import annotations

import pytest

from auto_invest.safety.autonomy import AutonomyLevel
from auto_invest.safety.boundary import (
    BoundarySurface,
    ProposedChange,
    SafetyBoundaryError,
    assert_autonomous_boundary_allowed,
    decide_boundary,
)


@pytest.mark.parametrize(
    ("path", "surface"),
    [
        ("src/auto_invest/config/caps.py", BoundarySurface.POSITION_CAPS),
        ("src/auto_invest/risk/gates.py", BoundarySurface.POSITION_CAPS),
        ("src/auto_invest/config/whitelist.py", BoundarySurface.WHITELIST),
        ("src/auto_invest/portfolio/capital_ladder.py", BoundarySurface.LOSS_BUDGET),
        (".github/workflows/go-live-canary.yml", BoundarySurface.LIVE_AUTHORITY),
        ("src/auto_invest/safety/autonomy.py", BoundarySurface.SAFETY_POLICY),
    ],
)
def test_protected_paths_are_a6_safety_boundary_changes(
    path: str,
    surface: BoundarySurface,
) -> None:
    decision = decide_boundary(ProposedChange(summary="tight scoped edit", paths=(path,)))

    assert decision.level is AutonomyLevel.SAFETY_BOUNDARY_CHANGE
    assert surface in decision.surfaces
    assert decision.autonomous_allowed is False
    assert decision.operator_approval_required is True
    assert decision.blocks_autonomous_execution is True


@pytest.mark.parametrize(
    ("summary", "surface"),
    [
        ("raise cap from 5 to 10 percent", BoundarySurface.POSITION_CAPS),
        ("add a new whitelist symbol", BoundarySurface.WHITELIST),
        ("change the drawdown budget for the ladder", BoundarySurface.LOSS_BUDGET),
        ("grant AUTO_INVEST_MODE=live authority", BoundarySurface.LIVE_AUTHORITY),
        ("rewrite the autonomy policy", BoundarySurface.SAFETY_POLICY),
    ],
)
def test_boundary_summary_keywords_are_a6_source_of_truth(
    summary: str,
    surface: BoundarySurface,
) -> None:
    decision = decide_boundary(ProposedChange(summary=summary))

    assert decision.level is AutonomyLevel.SAFETY_BOUNDARY_CHANGE
    assert decision.surfaces == frozenset({surface})
    assert decision.autonomous_allowed is False


def test_declared_boundary_surface_is_a6_even_without_path_or_keyword() -> None:
    decision = decide_boundary(
        ProposedChange(
            summary="operator-owned parameter adjustment",
            declared_surfaces=frozenset({BoundarySurface.LOSS_BUDGET}),
        )
    )

    assert decision.level is AutonomyLevel.SAFETY_BOUNDARY_CHANGE
    assert decision.surfaces == frozenset({BoundarySurface.LOSS_BUDGET})


def test_a6_boundary_change_raises_on_ordinary_autonomous_path() -> None:
    change = ProposedChange(
        summary="expand whitelist",
        paths=("src/auto_invest/config/whitelist.py",),
    )

    with pytest.raises(SafetyBoundaryError) as excinfo:
        assert_autonomous_boundary_allowed(change)

    assert excinfo.value.decision.level is AutonomyLevel.SAFETY_BOUNDARY_CHANGE
    assert BoundarySurface.WHITELIST in excinfo.value.decision.surfaces


def test_non_boundary_change_keeps_requested_level_and_can_run() -> None:
    change = ProposedChange(
        summary="add a read-only analytics report",
        paths=("src/auto_invest/analytics/strategy_monitor.py",),
        requested_level=AutonomyLevel.SIMULATION,
    )

    decision = assert_autonomous_boundary_allowed(change)

    assert decision.level is AutonomyLevel.SIMULATION
    assert decision.surfaces == frozenset()
    assert decision.autonomous_allowed is True
    assert decision.operator_approval_required is False
