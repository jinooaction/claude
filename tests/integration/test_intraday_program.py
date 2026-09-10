import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.broker.intraday_inputs import EXCHANGES, PREFIXES, SourceQuote
from auto_invest.execution.intraday import Decision
from auto_invest.execution.intraday_observation import ExecutionObserver
from auto_invest.execution.intraday_program import build_program
from auto_invest.execution.intraday_rehearsal import rehearsal_session
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import SYMBOLS, iso

PROVIDER = "kis-nasdaq-partial-unadjusted"
PREREG = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")


class LifecycleFeed:
    def __init__(self, *, fail=False):
        self.started = asyncio.Event()
        self.closed = asyncio.Event()
        self.calls = 0
        self.fail = fail

    def snapshot(self):
        # Lifecycle fixture deliberately retains keys after failure: terminal
        # task status must prevent entry independently of a stale cache.
        return dict.fromkeys(SYMBOLS)

    async def serve(self, *, approval):
        self.calls += 1
        self.started.set()
        try:
            await approval()
            if self.fail:
                raise RuntimeError("private credential details")
            await asyncio.Event().wait()
        finally:
            self.closed.set()


async def offline_approval():
    return "offline"


@pytest.mark.asyncio
@pytest.mark.parametrize("with_valuation", [False, True])
async def test_program_owns_quotes_only_after_database_lock_and_closes_on_stop(
    tmp_path, with_valuation,
):
    async with rehearsal_session(tmp_path / "simulation.db") as book:
        config = configuration(book)

        async def collect():
            await asyncio.Event().wait()

        config["collect_bars"] = collect
        feed = LifecycleFeed()
        valuation = LifecycleFeed() if with_valuation else None
        if valuation is not None:
            valuation.snapshot = lambda: dict.fromkeys(("SCHX", "IAUM"))
        program = replace(build_program(**config), quote_feed=feed, quote_approval=offline_approval,
                          valuation_feed=valuation)
        original = program.engine.entry_guard
        stop = asyncio.Event()
        task = asyncio.create_task(program.run(stop_event=stop, poll_seconds=.01))
        try:
            await asyncio.wait_for(feed.started.wait(), 2)
            if valuation is not None:
                await asyncio.wait_for(valuation.started.wait(), 2)
                assert program.engine.entry_guard() != "QUOTE_STREAM_UNAVAILABLE"
            guard = program.engine.entry_guard
            duplicate = await program.run(max_cycles=1)
            assert duplicate["phase"] == "ALREADY_RUNNING"
            assert duplicate["quote_state"] == "NOT_STARTED"
            assert feed.calls == 1
            assert program.engine.entry_guard is guard
            stop.set()
            done = await asyncio.wait_for(task, 2)
            assert done["phase"] == "STOPPED"
            assert done["quote_state"] == "CLOSED"
            assert feed.closed.is_set()
            if valuation is not None:
                assert valuation.closed.is_set() and valuation.calls == 1
            assert program.engine.entry_guard is original
            assert not book.orders
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task


@pytest.mark.asyncio
async def test_terminal_quote_task_blocks_entry_even_if_cache_retains_symbols(tmp_path):
    async with rehearsal_session(tmp_path / "simulation.db") as book:
        config = configuration(book)

        async def collect():
            await asyncio.Event().wait()

        config["collect_bars"] = collect
        feed = LifecycleFeed(fail=True)
        program = replace(build_program(**config), quote_feed=feed, quote_approval=offline_approval)
        stop = asyncio.Event()
        task = asyncio.create_task(program.run(stop_event=stop, poll_seconds=.01))
        try:
            await asyncio.wait_for(feed.closed.wait(), 2)
            assert program.engine.entry_guard() == "QUOTE_STREAM_UNAVAILABLE"
            assert not task.done()  # Existing order management still owns the ledger.
            stop.set()
            result = await asyncio.wait_for(task, 2)
            assert "private" not in str(result)
            assert result["phase"] == "STOPPED"
            assert not book.orders
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task


@pytest.mark.asyncio
async def test_cancellation_closes_quote_task_and_preserves_drain_for_restart(tmp_path):
    async with rehearsal_session(tmp_path / "simulation.db") as book:
        config = configuration(book)

        async def collect():
            await asyncio.Event().wait()

        config["collect_bars"] = collect
        feed = LifecycleFeed()
        program = replace(build_program(**config), quote_feed=feed, quote_approval=offline_approval)
        original = program.engine.entry_guard
        task = asyncio.create_task(program.run(poll_seconds=.01))
        await asyncio.wait_for(feed.started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert feed.closed.is_set()
        assert program.engine.entry_guard is original
        assert program.engine.drain_requested()
        assert (await program.run(max_cycles=1))["phase"] == "STOPPED"
        assert not program.engine.drain_requested()


@pytest.mark.asyncio
@pytest.mark.parametrize("shared", [False, True])
async def test_kis_assembly_uses_its_router_for_real_reads_and_refuses_unverified_scope(
    tmp_path, monkeypatch, shared,
):
    from auto_invest.broker.intraday_inputs import REST_URL
    from auto_invest.execution.intraday_program import build_kis_program

    calls = []
    synchronized_tokens = []

    async def sync(conn, broker, **kwargs):
        synchronized_tokens.append(kwargs["access_token"])
        assert kwargs["access_token"] == "fresh"
        return SimpleNamespace(error=None, warnings=[])

    monkeypatch.setattr("auto_invest.execution.intraday.sync_fills", sync)

    def handle(request):
        calls.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json=dict(access_token="fresh", expires_in=86400))
        assert request.method == "GET"
        rows = {
            "inquire-balance": dict(output1=[], ctx_area_fk200="", ctx_area_nk200=""),
            "inquire-nccs": dict(output=[], ctx_area_fk200="", ctx_area_nk200=""),
            "inquire-psamount": dict(output={"ovrs_ord_psbl_amt": "99999"}),
            "foreign-margin": dict(output=[]),
        }
        return httpx.Response(200, json=dict(rt_cd="0", **rows[request.url.path.rsplit("/", 1)[1]]))

    async with rehearsal_session(tmp_path / "simulation.db") as book:
        config = configuration(book)
        if shared:
            config["router"].conn.execute("""INSERT INTO current_positions
                (symbol, qty, avg_cost_usd, last_updated_utc)
                VALUES ('SCHX', 2, '20', '2026-09-10T14:00:00Z')""")
            config["router"].conn.commit()
        config.pop("observe")
        selection = config.pop("selection")
        config.pop("qualify")

        class Qualification:
            def __init__(self):
                self.selection = selection

            def __call__(self):
                return None

        async def prepare(**kwargs):
            assert kwargs["account"] == config["router"].account_no
            assert kwargs["capital_limit"] == config["capital_limit"]
            return Qualification()

        monkeypatch.setattr("auto_invest.execution.intraday_program.prepare_qualification", prepare)
        async with httpx.AsyncClient(
            base_url=REST_URL, transport=httpx.MockTransport(handle),
        ) as http:
            config["router"].broker._client = http
            program = await build_kis_program(
                **config, token_cache=tmp_path / "cache/token.json", archives=tmp_path,
                forward_database=tmp_path / "forward.db", registration=tmp_path / "freeze.json",
            )
            assert calls == []
            if shared:
                assert program.quote_feed.account_feed.symbols == ("SCHX",)
                assert dict(program.engine.external_holdings) == {}
            result = await program.engine.manage()
            assert result == dict(status="HALTED", reason="ACCOUNT_SCOPE_UNVERIFIED", actions=[])
            assert not book.orders
            assert program.engine.observe.authority is config["router"].execution_authority
            assert config["router"].execution_authority.access_token == "fresh"
            config["router"].halt_path = tmp_path / "different-halt"
            assert program.engine.guard() == "PROGRAM_AUTHORITY_REFUSED"
    assert [r.method for r in calls] == ["POST"] + ["GET"] * 4
    assert synchronized_tokens == ["fresh"]


def configuration(book):
    """Assembly fixture only; does not assert a real accepted research history."""
    candidate = build_candidate_registry(load_preregistration(PREREG))[0]
    selection = ResearchSelection(
        candidate, PROVIDER, "a" * 40, "sha256:" + "b" * 64, "sha256:" + "c" * 64,
        execution_fingerprint(candidate, PROVIDER), "PAPER_CHALLENGER", 756, 0,
    )

    async def account():
        observed = await book.observe()
        return dict(
            currency="USD", pagination_complete=True, full_account_scope_verified=True,
            cash_aggregation_verified=True, nav_verified=True, unverified_assets={},
            observation_started_at=book.now.isoformat(),
            observation_completed_at=book.now.isoformat(),
            execution_cash=str(observed.cash), nav=str(observed.nav),
            positions={s: dict(quantity=q, sellable_quantity=q)
                       for s, q in observed.positions.items()},
            open_orders=[dict(order_id=i) for i in observed.open_order_ids],
        )

    def quotes():
        return {s: SourceQuote(s, e, PREFIXES[e] + s, book.mark, None, None,
                               book.now, book.now, "20260909", "000000", "20260908", "110000", "1")
                for s, e in EXCHANGES.items()}

    async def collect():
        opening = book.now.replace(hour=13, minute=30)
        return [dict(symbol=s, timestamp_utc=iso(opening + timedelta(minutes=5 * i)),
                     open=20 + i, high=22 + i, low=19 + i, close=21 + i, volume=100000)
                for i in range(9) for s in SYMBOLS]

    return dict(
        selection=selection, router=book.engine.router,
        observe=ExecutionObserver(account, quotes, now=lambda: book.now),
        qualify=lambda: None, collect_bars=collect,
        capital_limit=Decimal("600"), now=lambda: book.now,
    )


@pytest.mark.asyncio
async def test_assembled_program_starts_and_resumes_stop_after_database_reopen(tmp_path):
    path = tmp_path / "simulation.db"
    async with rehearsal_session(path, capital_limit=Decimal("600"), mark=Decimal("29")) as book:
        book.now = book.now.replace(hour=14, minute=15)
        program = build_program(**configuration(book))
        state = await program.run(max_cycles=3, poll_seconds=.01)
        assert state["phase"] == "NEEDS_ATTENTION"
        assert book.orders
        buys = list(book.orders)
        for number in buys:
            book.fill(number, 1, "29")
        program.engine.request_drain()
        pending = await program.run(max_cycles=1)
        assert pending["phase"] == "NEEDS_ATTENTION"
        saved_orders, clock = book.orders, book.now

    async with rehearsal_session(path, capital_limit=Decimal("600"), mark=Decimal("29")) as book:
        book.orders, book.now = saved_orders, clock
        program = build_program(**configuration(book))
        assert program.engine.drain_requested()
        for number in buys:
            book.fill(number, 2, "29", terminal=True)
        pending = await program.run(max_cycles=1)
        assert pending["phase"] == "NEEDS_ATTENTION"
        sells = [n for n, row in book.orders.items() if row["sll_buy_dvsn_cd"] == "01"]
        assert len(sells) == len(buys)
        for number in sells:
            assert book.orders[number]["qty"] == 2
            book.fill(number, 2, "29")
        done = await program.run(max_cycles=1)
        assert done["phase"] == "STOPPED"
        assert done["owned_symbols"] == done["pending_orders"] == 0
        assert len(book.orders) == 2 * len(buys)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing", "identity", "capital", "authority", "account"])
async def test_invalid_assembly_is_rejected_before_changing_router_or_ledger(tmp_path, change):
    async with rehearsal_session(tmp_path / "simulation.db") as book:
        config = configuration(book)
        if change == "missing":
            config["selection"] = replace(config["selection"], candidate=None)
        elif change == "identity":
            config["selection"] = replace(config["selection"], execution_identity="b" * 64)
        elif change == "capital":
            config["capital_limit"] = Decimal("600.01")
        elif change == "authority":
            config["qualify"] = None
        else:
            book.engine.router.execution_authority.account_no = "9999999901"
        guard = book.engine.router.live_order_guard
        count = book.conn.total_changes
        with pytest.raises(ValueError, match="PROGRAM_"):
            build_program(**config)
        assert book.conn.total_changes == count
        assert book.engine.router.live_order_guard is guard
        assert book.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["candidate", "account", "capital", "refusal", "error"])
async def test_authority_and_configuration_are_rechecked_without_private_error_output(
    tmp_path, change,
):
    async with rehearsal_session(tmp_path / "simulation.db") as book:
        config = configuration(book)
        refusal = []

        def qualify():
            if refusal == ["error"]:
                raise RuntimeError("private credential")
            return "private credential" if refusal else None

        config["qualify"] = qualify
        program = build_program(**config)
        if change == "candidate":
            program.selection.candidate.parameters["threshold_bps"] = 999
        elif change == "account":
            book.engine.router.account_no = "9999999901"
        elif change == "capital":
            program.engine.capital_limit = Decimal("601")
        else:
            refusal.append(change)
        state = await program.run(max_cycles=1)
        assert state["last_result"]["status"] == "DENIED"
        assert "private" not in str(state)
        assert book.requests == []


@pytest.mark.asyncio
async def test_assembly_preserves_the_routers_existing_last_moment_guard(tmp_path):
    async with rehearsal_session(tmp_path / "simulation.db") as book:
        calls = []

        def deny():
            calls.append(True)
            return "EXISTING_WRITE_DENIAL"

        book.engine.router._intraday_original_guard = deny
        program = build_program(**configuration(book))
        decision = Decision(program.selection.execution_identity, book.now,
                            {"SPY": 1}, {"SPY": book.mark})
        await program.engine.step(decision)
        assert calls
        assert book.requests == []


@pytest.mark.asyncio
async def test_async_authority_is_rejected_instead_of_becoming_an_unawaited_permission(tmp_path):
    async with rehearsal_session(tmp_path / "simulation.db") as book:
        config = configuration(book)

        async def qualify():
            return None

        config["qualify"] = qualify
        with pytest.raises(ValueError, match="SYNCHRONOUS_AUTHORITY_REQUIRED"):
            build_program(**config)
