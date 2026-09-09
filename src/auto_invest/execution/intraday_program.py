"""Explicit assembly of the intraday program; no authority is issued here."""

import inspect
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from auto_invest.execution.intraday import IntradayExecutor
from auto_invest.execution.intraday_observation import KISExecutionObserver
from auto_invest.execution.intraday_runtime import run
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.execution.preparation import confirmed_budget
from auto_invest.market_data.intraday import SYMBOLS


@dataclass(frozen=True)
class IntradayProgram:
    engine: IntradayExecutor
    selection: ResearchSelection
    collect_bars: object

    async def run(self, **runtime_options):
        return await run(
            self.engine, candidate=self.selection.candidate, provider=self.selection.provider,
            collect_bars=self.collect_bars, **runtime_options,
        )


def build_kis_program(*, selection, router, quote_snapshot, token_cache, qualify,
                      collect_bars, capital_limit, external_holdings=None, now):
    """Bind real authenticated account reads to the same router's authority.

    Construction performs no network access or broker writes. Account valuation
    and qualification still have to pass before the executor can submit orders.
    """
    if router.execution_authority is None:
        raise ValueError("PROGRAM_ROUTER_CONFIGURATION_INVALID")
    observer = KISExecutionObserver(
        router.execution_authority, quote_snapshot, token_cache=token_cache, now=now,
    )
    return build_program(
        selection=selection, router=router, observe=observer, qualify=qualify,
        collect_bars=collect_bars, capital_limit=capital_limit,
        external_holdings=external_holdings, now=now,
    )


def build_program(
    *, selection, router, observe, qualify, collect_bars, capital_limit,
    external_holdings=None, now,
):
    """Compose trusted in-process dependencies; no user-imported plugin or PASS flag.

    qualify is the launching integration's reviewed execution-authority check,
    not a report's live_eligible field. This assembly does not implement that
    provider; it requires it explicitly and repeats it at the broker boundary.
    """
    if (not isinstance(selection, ResearchSelection) or selection.candidate is None
            or selection.verdict != "PAPER_CHALLENGER"
            or selection.provider != "kis-nasdaq-partial-unadjusted"
            or selection.execution_identity != execution_fingerprint(
                selection.candidate, selection.provider,
            )):
        raise ValueError("PROGRAM_RESEARCH_IDENTITY_INVALID")
    if any(not callable(value) for value in (observe, qualify, collect_bars, now)):
        raise ValueError("PROGRAM_DEPENDENCY_REQUIRED")
    if (inspect.iscoroutinefunction(qualify)
            or inspect.iscoroutinefunction(qualify.__call__)):
        raise ValueError("PROGRAM_SYNCHRONOUS_AUTHORITY_REQUIRED")
    root = Path(__file__).resolve().parents[3]
    budget = confirmed_budget(
        root / "specs/182-intraday-kis-execution/contracts/confirmed-budget.json",
    )
    if (not isinstance(capital_limit, Decimal) or not capital_limit.is_finite()
            or not 0 < capital_limit <= Decimal(budget["capital_limit_usd"])):
        raise ValueError("PROGRAM_CAPITAL_LIMIT_INVALID")
    account = router.account_no
    if (router.paper_mode or account not in router.whitelist.accounts
            or not set(SYMBOLS) <= router.whitelist.symbols
            or router.execution_authority is None
            or router.execution_authority.account_no != account
            or router.execution_authority.conn is not router.conn
            or router.execution_authority.broker is not router.broker):
        raise ValueError("PROGRAM_ROUTER_CONFIGURATION_INVALID")
    identity = selection.execution_identity

    def guard():
        try:
            if (router.account_no != account or router.execution_authority.account_no != account
                    or router.execution_authority.conn is not router.conn
                    or router.execution_authority.broker is not router.broker
                    or account not in router.whitelist.accounts):
                return "PROGRAM_ACCOUNT_CHANGED"
            if engine.capital_limit != capital_limit:
                return "PROGRAM_CAPITAL_CHANGED"
            if execution_fingerprint(selection.candidate, selection.provider) != identity:
                return "PROGRAM_STRATEGY_CHANGED"
            reason = qualify()
            if reason is not None:
                # The caller's diagnostic can contain private broker context.
                return "PROGRAM_AUTHORITY_REFUSED"
        except Exception:
            return "PROGRAM_AUTHORITY_UNAVAILABLE"
        return None

    engine = IntradayExecutor(
        router, fingerprint=identity, observe=observe, authority_guard=guard,
        capital_limit=capital_limit, now=now, external_holdings=external_holdings,
    )
    return IntradayProgram(engine, selection, collect_bars)
