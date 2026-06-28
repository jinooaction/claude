"""CLI command safety registry.

This registry is the executable risk matrix for operator commands. It is kept
in code so tests can enforce coverage and invariants as the CLI evolves.
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.safety.autonomy import AutonomyLevel, policy_for


@dataclass(frozen=True)
class CommandPolicy:
    name: str
    level: AutonomyLevel
    description: str
    can_place_order: bool = False
    can_change_live_config: bool = False
    can_scale_capital: bool = False
    can_reassign_strategy: bool = False
    requires_operator_boundary: bool = False
    writes_db: bool = False
    uses_broker: bool = False
    uses_llm: bool = False

    def to_json_dict(self) -> dict[str, object]:
        level_policy = policy_for(self.level)
        return {
            "name": self.name,
            "level": self.level.value,
            "level_label": level_policy.label,
            "description": self.description,
            "autonomous_allowed": level_policy.autonomous_allowed,
            "operator_approval_required": (
                self.requires_operator_boundary
                or level_policy.operator_approval_required
            ),
            "can_place_order": self.can_place_order,
            "can_change_live_config": self.can_change_live_config,
            "can_scale_capital": self.can_scale_capital,
            "can_reassign_strategy": self.can_reassign_strategy,
            "writes_db": self.writes_db,
            "uses_broker": self.uses_broker,
            "uses_llm": self.uses_llm,
        }


def _p(
    name: str,
    level: AutonomyLevel,
    description: str,
    **kwargs: object,
) -> CommandPolicy:
    return CommandPolicy(name=name, level=level, description=description, **kwargs)


COMMAND_POLICIES: dict[str, CommandPolicy] = {
    "account-nav": _p(
        "account-nav",
        AutonomyLevel.READ_ONLY,
        "Read KIS account NAV for operator visibility.",
        uses_broker=True,
    ),
    "autoarm-decide": _p(
        "autoarm-decide",
        AutonomyLevel.CAPITAL_SCALING,
        "Decide whether measured evidence permits live capital arming.",
        can_scale_capital=True,
    ),
    "backfill-bars": _p(
        "backfill-bars",
        AutonomyLevel.PROPOSAL,
        "Fetch and persist historical bars; no orders.",
        writes_db=True,
        uses_broker=True,
    ),
    "backtest": _p(
        "backtest",
        AutonomyLevel.SIMULATION,
        "Replay rules against historical data.",
        writes_db=True,
    ),
    "backtest-portfolio": _p(
        "backtest-portfolio",
        AutonomyLevel.SIMULATION,
        "Replay portfolio rebalance logic against historical data.",
    ),
    "bars-export": _p(
        "bars-export",
        AutonomyLevel.READ_ONLY,
        "Export stored OHLCV bars.",
    ),
    "bars-status": _p(
        "bars-status",
        AutonomyLevel.READ_ONLY,
        "Inspect stored OHLCV coverage.",
    ),
    "build-universe": _p(
        "build-universe",
        AutonomyLevel.PROPOSAL,
        "Build a candidate universe file from market data.",
    ),
    "canary-portfolio": _p(
        "canary-portfolio",
        AutonomyLevel.SIMULATION,
        "Run canary portfolio validation; no live order placement.",
        writes_db=True,
    ),
    "collect-public-data": _p(
        "collect-public-data",
        AutonomyLevel.PROPOSAL,
        "Collect and persist public market data.",
        writes_db=True,
    ),
    "db migrate": _p(
        "db migrate",
        AutonomyLevel.PROPOSAL,
        "Apply schema migrations; changes local persistence only.",
        writes_db=True,
    ),
    "deploy": _p(
        "deploy",
        AutonomyLevel.PROPOSAL,
        "Deploy code under off-hours guards; does not itself place orders.",
        writes_db=True,
    ),
    "design": _p(
        "design",
        AutonomyLevel.BOUNDED_LIVE,
        "Use LLM-assisted rule design and optionally start a live worker after operator OK.",
        can_place_order=True,
        can_change_live_config=True,
        writes_db=True,
        uses_broker=True,
        uses_llm=True,
    ),
    "efficiency": _p(
        "efficiency",
        AutonomyLevel.READ_ONLY,
        "Report LLM token efficiency metrics; records price-table audit metadata.",
        writes_db=True,
    ),
    "evolution-scan": _p(
        "evolution-scan",
        AutonomyLevel.READ_ONLY,
        "Read collected evidence and render autonomous-evolution candidates; "
        "no orders or live config changes.",
    ),
    "promotion-scan": _p(
        "promotion-scan",
        AutonomyLevel.READ_ONLY,
        "Classify autonomous-evolution candidates into promotion stages; "
        "no orders or live config changes.",
    ),
    "candidate-factory": _p(
        "candidate-factory",
        AutonomyLevel.READ_ONLY,
        "Build candidate implementation packages and enriched backlog evidence; "
        "no orders, broker calls, capital scaling, or live config changes.",
    ),
    "promotion-actions": _p(
        "promotion-actions",
        AutonomyLevel.PROPOSAL,
        "Build promotion-only forward paper registrations and canary submissions; "
        "no orders, broker calls, capital scaling, or live config changes.",
    ),
    "fills": _p(
        "fills",
        AutonomyLevel.PROPOSAL,
        "Inspect or sync broker fills into local state; no new orders.",
        writes_db=True,
        uses_broker=True,
    ),
    "forward-verdict": _p(
        "forward-verdict",
        AutonomyLevel.PROPOSAL,
        "Evaluate forward evidence and emit a promotion verdict.",
    ),
    "forward-verdict-anchored": _p(
        "forward-verdict-anchored",
        AutonomyLevel.PROPOSAL,
        "Evaluate anchored forward evidence and emit a promotion verdict.",
    ),
    "growth": _p(
        "growth",
        AutonomyLevel.READ_ONLY,
        "Report growth and leverage analytics.",
    ),
    "halt": _p(
        "halt",
        AutonomyLevel.BOUNDED_LIVE,
        "Set the persistent halt flag to block live order submission.",
        writes_db=True,
    ),
    "health": _p(
        "health",
        AutonomyLevel.READ_ONLY,
        "Read-only operational health check.",
    ),
    "ingest-history": _p(
        "ingest-history",
        AutonomyLevel.PROPOSAL,
        "Ingest historical OHLCV data into local storage.",
        writes_db=True,
    ),
    "ladder-decide": _p(
        "ladder-decide",
        AutonomyLevel.CAPITAL_SCALING,
        "Decide capital ladder promotion, demotion, or halt.",
        can_scale_capital=True,
    ),
    "macro-regime": _p(
        "macro-regime",
        AutonomyLevel.READ_ONLY,
        "Report macro regime classification.",
    ),
    "nav-snapshot": _p(
        "nav-snapshot",
        AutonomyLevel.PROPOSAL,
        "Record or inspect a portfolio NAV snapshot.",
        writes_db=True,
    ),
    "opportunity-monitor": _p(
        "opportunity-monitor",
        AutonomyLevel.PROPOSAL,
        "Update rejected-order opportunity history and emit review signals; no orders.",
    ),
    "paper-report": _p(
        "paper-report",
        AutonomyLevel.READ_ONLY,
        "Summarize paper-run audit events.",
    ),
    "paper-run": _p(
        "paper-run",
        AutonomyLevel.SIMULATION,
        "Run live-quote paper trading with simulated fills only.",
        writes_db=True,
        uses_broker=True,
    ),
    "performance": _p(
        "performance",
        AutonomyLevel.READ_ONLY,
        "Compute live or paper performance; optional snapshot writes audit metadata.",
        writes_db=True,
        uses_broker=True,
    ),
    "portfolio-walk-forward": _p(
        "portfolio-walk-forward",
        AutonomyLevel.SIMULATION,
        "Run portfolio walk-forward validation.",
    ),
    "promote-check": _p(
        "promote-check",
        AutonomyLevel.PROPOSAL,
        "Check whether live canary evidence is ready for promotion.",
    ),
    "rebalance-once": _p(
        "rebalance-once",
        AutonomyLevel.BOUNDED_LIVE,
        "Plan or execute a single rebalance through live risk gates.",
        can_place_order=True,
        writes_db=True,
        uses_broker=True,
    ),
    "rejected-order-opportunity": _p(
        "rejected-order-opportunity",
        AutonomyLevel.READ_ONLY,
        "Evaluate current-mark opportunity PnL for rejected rebalance orders.",
        uses_broker=True,
    ),
    "reassign-challenger-path": _p(
        "reassign-challenger-path",
        AutonomyLevel.STRATEGY_REASSIGNMENT,
        "Identify the challenger strategy path from a leaderboard.",
        can_reassign_strategy=True,
    ),
    "reassign-decide": _p(
        "reassign-decide",
        AutonomyLevel.STRATEGY_REASSIGNMENT,
        "Decide whether five-gate strategy reassignment is permitted.",
        can_reassign_strategy=True,
    ),
    "reconcile": _p(
        "reconcile",
        AutonomyLevel.BOUNDED_LIVE,
        "Compare local state with broker state and halt on mismatch.",
        writes_db=True,
        uses_broker=True,
    ),
    "regime-stratify": _p(
        "regime-stratify",
        AutonomyLevel.READ_ONLY,
        "Analyze strategy behavior by regime.",
    ),
    "report": _p(
        "report",
        AutonomyLevel.READ_ONLY,
        "Render a daily activity report from audit state.",
    ),
    "resume": _p(
        "resume",
        AutonomyLevel.BOUNDED_LIVE,
        "Clear the persistent halt flag after operator confirmation.",
        writes_db=True,
    ),
    "run": _p(
        "run",
        AutonomyLevel.BOUNDED_LIVE,
        "Run the live worker; dry-run validates without broker order placement.",
        can_place_order=True,
        writes_db=True,
        uses_broker=True,
    ),
    "safety commands": _p(
        "safety commands",
        AutonomyLevel.READ_ONLY,
        "Render the executable command safety registry.",
    ),
    "signal-ic": _p(
        "signal-ic",
        AutonomyLevel.READ_ONLY,
        "Measure signal information coefficient.",
    ),
    "status": _p(
        "status",
        AutonomyLevel.READ_ONLY,
        "Read one-screen operator status.",
    ),
    "telegram-alerts": _p(
        "telegram-alerts",
        AutonomyLevel.PROPOSAL,
        "Read audit_log and send best-effort Telegram operator alerts; no orders.",
    ),
    "tune": _p(
        "tune",
        AutonomyLevel.PROPOSAL,
        "Run autonomous tuner within its coded authority.",
        writes_db=True,
    ),
    "version": _p(
        "version",
        AutonomyLevel.READ_ONLY,
        "Print package version.",
    ),
    "walk-forward": _p(
        "walk-forward",
        AutonomyLevel.SIMULATION,
        "Run walk-forward validation.",
    ),
}


def command_policies() -> dict[str, CommandPolicy]:
    return dict(sorted(COMMAND_POLICIES.items()))


def command_policy(name: str) -> CommandPolicy:
    return COMMAND_POLICIES[name]
