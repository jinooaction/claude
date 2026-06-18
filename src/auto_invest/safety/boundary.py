"""Executable safety-boundary guard.

The safety boundary is code-owned. Documentation can explain this model, but
autonomous paths must call this module before applying a proposed change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from auto_invest.safety.autonomy import AutonomyLevel, policy_for


class BoundarySurface(StrEnum):
    """Safety surfaces that cannot be changed by ordinary autonomous paths."""

    POSITION_CAPS = "position_caps"
    WHITELIST = "whitelist"
    LOSS_BUDGET = "loss_budget"
    LIVE_AUTHORITY = "live_authority"
    SAFETY_POLICY = "safety_policy"


SAFETY_BOUNDARY_SURFACES: frozenset[BoundarySurface] = frozenset(BoundarySurface)


_SURFACE_PATHS: dict[BoundarySurface, tuple[str, ...]] = {
    BoundarySurface.POSITION_CAPS: (
        "src/auto_invest/config/caps.py",
        "src/auto_invest/risk/gates.py",
        "src/auto_invest/risk/circuit_breaker.py",
        "src/auto_invest/risk/",
    ),
    BoundarySurface.WHITELIST: (
        "src/auto_invest/config/whitelist.py",
    ),
    BoundarySurface.LOSS_BUDGET: (
        "src/auto_invest/portfolio/capital_ladder.py",
        "src/auto_invest/portfolio/reassign_exec.py",
        "src/auto_invest/analytics/money_path.py",
        "automation/AUTOARM_DISABLED",
        ".github/workflows/forward-edge-autoarm.yml",
        ".github/workflows/reassign-on-tournament.yml",
    ),
    BoundarySurface.LIVE_AUTHORITY: (
        "automation/go-live-canary.request",
        ".github/workflows/go-live-canary.yml",
        ".github/workflows/rebalance-live-canary.yml",
        ".github/workflows/deploy-on-merge.yml",
        "deploy/go-live-canary.sh",
    ),
    BoundarySurface.SAFETY_POLICY: (
        "src/auto_invest/safety/",
        ".specify/memory/constitution.md",
        ".specify/memory/kernel.toml",
    ),
}

_SURFACE_KEYWORDS: dict[BoundarySurface, tuple[str, ...]] = {
    BoundarySurface.POSITION_CAPS: (
        "cap",
        "caps",
        "position cap",
        "exposure cap",
        "sizing cap",
    ),
    BoundarySurface.WHITELIST: (
        "whitelist",
        "allowlist",
        "allowed symbol",
        "tradeable symbol",
    ),
    BoundarySurface.LOSS_BUDGET: (
        "loss budget",
        "drawdown budget",
        "dd budget",
        "daily loss limit",
        "max total drawdown",
    ),
    BoundarySurface.LIVE_AUTHORITY: (
        "live authority",
        "auto_invest_mode=live",
        "go live",
        "live canary",
        "real order authority",
    ),
    BoundarySurface.SAFETY_POLICY: (
        "safety policy",
        "autonomy policy",
        "boundary policy",
        "safety perimeter",
        "kernel",
    ),
}


@dataclass(frozen=True)
class ProposedChange:
    """Pure description of a change before an autonomous actor applies it."""

    summary: str
    paths: tuple[str, ...] = ()
    declared_surfaces: frozenset[BoundarySurface] = field(default_factory=frozenset)
    requested_level: AutonomyLevel = AutonomyLevel.PROPOSAL

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", tuple(_normalize_path(p) for p in self.paths))
        object.__setattr__(
            self,
            "declared_surfaces",
            frozenset(BoundarySurface(s) for s in self.declared_surfaces),
        )


@dataclass(frozen=True)
class BoundaryDecision:
    """Decision returned by the safety-boundary classifier."""

    change: ProposedChange
    level: AutonomyLevel
    surfaces: frozenset[BoundarySurface]
    autonomous_allowed: bool
    operator_approval_required: bool
    reasons: tuple[str, ...]

    @property
    def blocks_autonomous_execution(self) -> bool:
        return not self.autonomous_allowed


class SafetyBoundaryError(RuntimeError):
    """Raised when an autonomous path attempts an A6 boundary change."""

    def __init__(self, decision: BoundaryDecision) -> None:
        self.decision = decision
        surfaces = ", ".join(sorted(s.value for s in decision.surfaces))
        super().__init__(
            "A6 safety-boundary change cannot run through the ordinary "
            f"autonomous path: {surfaces}"
        )


def decide_boundary(change: ProposedChange) -> BoundaryDecision:
    """Classify a proposed change and return the executable boundary decision."""

    surfaces = _detect_surfaces(change)
    level = (
        AutonomyLevel.SAFETY_BOUNDARY_CHANGE
        if surfaces
        else change.requested_level
    )
    level_policy = policy_for(level)
    reasons = _reasons(change, surfaces)
    return BoundaryDecision(
        change=change,
        level=level,
        surfaces=surfaces,
        autonomous_allowed=level_policy.autonomous_allowed,
        operator_approval_required=level_policy.operator_approval_required,
        reasons=reasons,
    )


def assert_autonomous_boundary_allowed(change: ProposedChange) -> BoundaryDecision:
    """Return the decision, or raise if the change is A6 and therefore blocked."""

    decision = decide_boundary(change)
    if decision.blocks_autonomous_execution:
        raise SafetyBoundaryError(decision)
    return decision


def _detect_surfaces(change: ProposedChange) -> frozenset[BoundarySurface]:
    detected = set(change.declared_surfaces)
    summary = change.summary.lower()

    for surface, paths in _SURFACE_PATHS.items():
        if any(_path_matches(path, prefixes=paths) for path in change.paths):
            detected.add(surface)

    for surface, keywords in _SURFACE_KEYWORDS.items():
        if any(keyword in summary for keyword in keywords):
            detected.add(surface)

    return frozenset(detected & SAFETY_BOUNDARY_SURFACES)


def _reasons(
    change: ProposedChange,
    surfaces: frozenset[BoundarySurface],
) -> tuple[str, ...]:
    if not surfaces:
        return ("no safety-boundary surface detected",)

    reasons: list[str] = []
    for surface in sorted(surfaces, key=lambda s: s.value):
        matched_paths = tuple(
            path
            for path in change.paths
            if _path_matches(path, prefixes=_SURFACE_PATHS[surface])
        )
        if matched_paths:
            reasons.append(
                f"{surface.value}: protected path(s) {', '.join(matched_paths)}"
            )
        else:
            reasons.append(f"{surface.value}: declared or summary-matched boundary")
    return tuple(reasons)


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/").removeprefix("./")


def _path_matches(path: str, *, prefixes: tuple[str, ...]) -> bool:
    normalized = _normalize_path(path)
    for prefix in prefixes:
        clean_prefix = _normalize_path(prefix)
        if clean_prefix.endswith("/"):
            if normalized.startswith(clean_prefix):
                return True
        elif normalized == clean_prefix:
            return True
    return False
