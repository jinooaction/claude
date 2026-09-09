"""Explicit assembly of the intraday program; no authority is issued here."""

import asyncio
import hashlib
import inspect
import json
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from auto_invest.broker.intraday_inputs import StrictQuoteFeed, approval_key
from auto_invest.execution.intraday import IntradayExecutor
from auto_invest.execution.intraday_observation import KISExecutionObserver
from auto_invest.execution.intraday_qualification import prepare_qualification
from auto_invest.execution.intraday_runtime import run
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.execution.preparation import confirmed_budget
from auto_invest.market_data.intraday import SYMBOLS


def runtime_identity(router, baseline):
    """Bind the operating approval to the actual ledger, halt path and risk config."""
    database = router.conn.execute("PRAGMA database_list").fetchone()[2]
    payload = dict(
        database=str(Path(database).resolve()), halt_path=str(router.halt_path.resolve()),
        whitelist=router.whitelist.model_dump(mode="json"),
        caps=router.caps.model_dump(mode="json"), external_holdings=baseline,
    )
    # Whitelist uses sets; JSON list ordering must not change an approval identity.
    for name, value in payload["whitelist"].items():
        if isinstance(value, list):
            payload["whitelist"][name] = sorted(value)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class IntradayProgram:
    engine: IntradayExecutor
    selection: ResearchSelection
    collect_bars: object
    quote_feed: StrictQuoteFeed | None = None
    quote_approval: object = None

    async def run(self, **runtime_options):
        async def execute(**resources):
            return await run(
                self.engine, candidate=self.selection.candidate, provider=self.selection.provider,
                collect_bars=self.collect_bars, **runtime_options, **resources,
            )

        if self.quote_feed is None:
            return await execute()
        if not callable(self.quote_approval):
            raise ValueError("PROGRAM_QUOTE_APPROVAL_REQUIRED")
        terminal = False
        started = False

        async def serve():
            nonlocal terminal
            try:
                await self.quote_feed.serve(approval=self.quote_approval)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Broker response text and authentication details stay private.
                pass
            finally:
                terminal = True

        @asynccontextmanager
        async def inputs():
            nonlocal started
            previous = self.engine.entry_guard

            def entry_guard():
                if terminal or set(self.quote_feed.snapshot()) != set(SYMBOLS):
                    return "QUOTE_STREAM_UNAVAILABLE"
                return previous()

            self.engine.entry_guard = entry_guard
            started = True
            quotes = asyncio.create_task(serve())
            try:
                yield
            finally:
                quotes.cancel()
                try:
                    with suppress(asyncio.CancelledError):
                        await quotes
                finally:
                    self.engine.entry_guard = previous

        result = await execute(resource_manager=inputs())
        return dict(result, quote_state="CLOSED" if started else "NOT_STARTED")


def build_kis_program(*, router, token_cache, archives, forward_database, registration,
                      collect_bars, capital_limit, external_holdings=None, now):
    """Bind real authenticated account reads to the same router's authority.

    Construction performs no network access or broker writes. Account valuation
    and qualification still have to pass before the executor can submit orders.
    """
    if router.execution_authority is None:
        raise ValueError("PROGRAM_ROUTER_CONFIGURATION_INVALID")
    baseline = dict(external_holdings or {})
    runtime_digest = runtime_identity(router, baseline)
    qualification = prepare_qualification(
        archives=archives, forward_database=forward_database, registration=registration,
        account=router.account_no, capital_limit=capital_limit, runtime_digest=runtime_digest,
    )
    if refusal := qualification():
        raise ValueError(refusal)
    feed = StrictQuoteFeed(now=now)
    observer = KISExecutionObserver(
        router.execution_authority, feed.snapshot, token_cache=token_cache, now=now,
    )

    async def refresh_auth():
        await observer.refresh_credentials()
        router.access_token = router.execution_authority.access_token

    def qualify():
        if runtime_identity(router, baseline) != runtime_digest:
            return "PROGRAM_RUNTIME_CONFIGURATION_CHANGED"
        return qualification()

    program = build_program(
        selection=qualification.selection, router=router, observe=observer, qualify=qualify,
        collect_bars=collect_bars, capital_limit=capital_limit,
        external_holdings=baseline, now=now, refresh_auth=refresh_auth,
    )

    async def approval():
        observer._check_connection()
        key = await approval_key(
            observer.broker, app_key=observer.authority.app_key,
            app_secret=observer.authority.app_secret,
        )
        observer._check_connection()
        return key

    return replace(program, quote_feed=feed, quote_approval=approval)


def build_program(
    *, selection, router, observe, qualify, collect_bars, capital_limit,
    external_holdings=None, now, refresh_auth=None,
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
        refresh_auth=refresh_auth,
    )
    return IntradayProgram(engine, selection, collect_bars)
