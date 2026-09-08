"""Actual execution coordinator/lifecycle against an offline KIS wire simulator."""

import asyncio
import json
import os
import sys
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_operator import publish
from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.execution.intraday import IntradayExecutor
from auto_invest.execution.intraday_rehearsal import FINGERPRINT, rehearsal_session
from auto_invest.execution.intraday_runtime import request_stop, run, state_directory, status
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import SYMBOLS, iso

PROVIDER = "kis-nasdaq-partial-unadjusted"


async def unavailable():
    raise RuntimeError("private upstream response must never appear in public state")


async def wait_until(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(.01)


def signals(book):
    candidate = build_candidate_registry(load_preregistration(
        Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
    ))[0]
    opening = book.now.replace(hour=13, minute=30)
    book.now = opening + timedelta(minutes=45)
    bars = [
        dict(
            symbol=symbol, timestamp_utc=iso(opening + timedelta(minutes=5 * n)),
            open=100 + n, high=102 + n, low=99 + n, close=101 + n, volume=100000,
        )
        for n in range(9) for symbol in SYMBOLS
    ]
    book.mark = Decimal("109")
    book.engine = IntradayExecutor(
        book.engine.router, fingerprint=execution_fingerprint(candidate, PROVIDER),
        observe=book.observe, authority_guard=lambda: None, capital_limit=book.initial_cash,
        now=lambda: book.now,
    )
    return candidate, bars


@pytest.mark.asyncio
async def test_management_preserves_young_buy_and_cancels_only_at_ttl(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 2, "100")
        result = await book.engine.manage()
        assert result == dict(status="WAIT_BROKER", actions=[])
        assert len(book.requests) == 1
        book.now += timedelta(minutes=5)
        result = await book.engine.manage()
        assert result["actions"] == [dict(kind="CANCEL_REQUEST", result="ACKNOWLEDGED")]
        assert len(book.requests) == 2


@pytest.mark.asyncio
async def test_management_never_reopens_filled_or_cancelled_buy(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 2, "100", terminal=True)
        assert (await book.engine.manage())["status"] == "MANAGED"
        assert (await book.engine.manage())["actions"] == []
        assert len(book.requests) == 1
        assert book.engine._owned() == {"SPY": 2}


@pytest.mark.asyncio
async def test_persistent_drain_cancels_late_fill_and_completes_only_after_sell_fill(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 2, "100")
        book.engine.request_drain()
        book.engine.request_drain()
        assert book.conn.execute(
            "SELECT COUNT(*) FROM intraday_execution_events WHERE kind='STOP_REQUESTED'"
        ).fetchone()[0] == 1
        result = await book.engine.manage()
        assert result["actions"][0]["kind"] == "CANCEL_REQUEST"
        book.fill("1", 3, "100", terminal=True)
        orders = book.orders
    async with rehearsal_session(database) as book:
        book.orders = orders
        assert book.engine.drain_requested()
        result = await book.engine.manage()
        assert result["status"] == "EXIT_ONLY", result
        assert book.orders["2"]["qty"] == 3
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
        assert book.engine.drain_requested()
        assert (await book.engine.manage())["status"] == "WAIT_BROKER"
        book.fill("2", 3, "100")
        assert (await book.engine.manage()) == dict(status="STOPPED", actions=[])
        assert not book.engine.drain_requested()
        assert book.engine._owned() == {}


@pytest.mark.asyncio
async def test_two_drain_cycles_same_day_have_distinct_sell_claims(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        for buy, sell in (("1", "2"), ("3", "4")):
            await book.engine.step(book.decision(5))
            book.fill(buy, 5, "100")
            book.engine.request_drain()
            assert (await book.engine.manage())["actions"][0]["kind"] == "SUBMITTED"
            book.fill(sell, 5, "100")
            assert (await book.engine.manage())["status"] == "STOPPED"
            book.now += timedelta(minutes=5)
        assert len(book.requests) == 4


@pytest.mark.asyncio
async def test_drain_with_stale_quote_can_cancel_but_cannot_submit_sell(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 2, "100")
        observe = book.observe

        async def stale():
            value = await observe()
            return replace(
                value, mark_times={s: book.now - timedelta(seconds=31) for s in value.marks}
            )

        book.engine.observe = stale
        book.engine.request_drain()
        assert (await book.engine.manage())["actions"][0]["kind"] == "CANCEL_REQUEST"
        book.fill("1", 2, "100", terminal=True)
        assert (await book.engine.manage())["reason"] == "STALE_EXECUTION_MARK"
        assert len(book.requests) == 2
        assert book.engine.drain_requested()


@pytest.mark.asyncio
async def test_management_handles_market_close_without_any_bars(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 5, "100")
        book.now = book.now.replace(hour=19, minute=45)
        result = await book.engine.manage()
        assert result["status"] == "EXIT_ONLY"
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"


@pytest.mark.asyncio
async def test_stop_last_moment_prevents_a_new_buy(tmp_path):
    from contextlib import asynccontextmanager

    async with rehearsal_session(tmp_path / "test.db") as book:
        original = book.engine.router.execution_authority.account_lock

        @asynccontextmanager
        async def stopping_lock(context):
            async with original(context):
                book.engine.request_drain()
                yield

        book.engine.router.execution_authority.account_lock = stopping_lock
        result = await book.engine.step(book.decision(5))
        assert result["actions"][0]["kind"] == "REJECTED_BY_GATE"
        assert book.requests == []
        assert book.engine.drain_requested()


@pytest.mark.asyncio
async def test_runtime_real_signal_reaches_order_and_stop_drains(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        candidate, bars = signals(book)

        async def collect():
            return bars

        task = asyncio.create_task(run(
            book.engine, candidate=candidate, provider=PROVIDER, collect_bars=collect,
            poll_seconds=.01, collection_seconds=60,
        ))
        try:
            await wait_until(lambda: len(book.orders) == 1)
            assert status(database)["running"]
            assert request_stop(database)["phase"] == "STOP_REQUESTED"
            await wait_until(lambda: len(book.requests) == 2)
            assert status(database)["phase"] != "STOPPED"
            book.fill("1", 2, "109", terminal=True)
            await wait_until(lambda: len(book.orders) == 2)
            assert book.orders["2"]["qty"] == 2
            assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
            book.fill("2", 2, "109")
            result = await asyncio.wait_for(task, 3)
            assert result["phase"] == "STOPPED"
            assert result["owned_symbols"] == result["pending_orders"] == 0
            assert not result["entries_enabled"]
            assert not status(database)["running"]
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task


@pytest.mark.asyncio
@pytest.mark.parametrize("hang", [False, True])
async def test_collector_failure_does_not_block_existing_order_cancel(tmp_path, hang):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        started = asyncio.Event()

        async def collect():
            started.set()
            book.now += timedelta(minutes=5)
            if hang:
                await asyncio.sleep(999)
            return await unavailable()

        result = await run(
            book.engine, candidate=None, provider=PROVIDER, collect_bars=collect,
            poll_seconds=.01, collection_seconds=60, collection_timeout=.02, max_cycles=8,
        )
        assert started.is_set()
        assert result["phase"] == "NEEDS_ATTENTION"
        assert result["signal_state"] == "UNAVAILABLE"
        assert len(book.requests) == 2
        assert book.requests[-1][0].endswith("/order-rvsecncl")
        assert "private upstream" not in str(result)


@pytest.mark.asyncio
async def test_same_database_alias_cannot_start_second_runtime(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        started = asyncio.Event()

        async def collect():
            started.set()
            await asyncio.sleep(999)

        stop = asyncio.Event()
        task = asyncio.create_task(run(
            book.engine, candidate=None, provider=PROVIDER, collect_bars=collect,
            stop_event=stop, poll_seconds=.01,
        ))
        try:
            await asyncio.wait_for(started.wait(), 3)
            alias = tmp_path / "alias.db"
            alias.symlink_to(database)
            assert state_directory(alias) == state_directory(database)
            duplicate = await run(
                book.engine, candidate=None, provider=PROVIDER, collect_bars=unavailable,
            )
            assert duplicate["phase"] == "ALREADY_RUNNING"
            assert request_stop(alias)["phase"] == "STOP_REQUESTED"
            assert (await asyncio.wait_for(task, 3))["phase"] == "STOPPED"
        finally:
            stop.set()
            if not task.done():
                await asyncio.wait_for(task, 3)


@pytest.mark.asyncio
async def test_stop_file_survives_crash_before_engine_acknowledges_request(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        await book.engine.step(book.decision(5))
        root = state_directory(database)
        root.mkdir()
        publish(root, "status.json", dict(
            run_id="previous-run", fingerprint=FINGERPRINT, phase="RUNNING",
        ))
        publish(root, "stop.json", dict(run_id="previous-run"))
        result = await run(
            book.engine, candidate=None, provider=PROVIDER, collect_bars=unavailable, max_cycles=1,
        )
        assert result["phase"] == "NEEDS_ATTENTION"
        assert book.engine.drain_requested()
        assert book.requests[-1][0].endswith("/order-rvsecncl")


@pytest.mark.asyncio
async def test_stale_stop_file_is_ignored_and_authority_is_not_granted(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        root = state_directory(database)
        root.mkdir()
        publish(root, "status.json", dict(run_id="newer", fingerprint=FINGERPRINT, phase="RUNNING"))
        publish(root, "stop.json", dict(run_id="old"))
        engine = IntradayExecutor(
            book.engine.router, fingerprint=FINGERPRINT, observe=book.observe, now=lambda: book.now,
        )
        called = []

        async def collect():
            called.append(True)
            return []

        result = await run(
            engine, candidate=None, provider=PROVIDER, collect_bars=collect, max_cycles=2,
            poll_seconds=.01,
        )
        assert result["phase"] == "NEEDS_ATTENTION"
        assert result["last_result"]["reason"] == "INTRADAY_AUTHORIZATION_REQUIRED"
        assert not engine.drain_requested()
        assert called == book.requests == []


@pytest.mark.asyncio
async def test_cancelled_runtime_persists_stop_and_releases_lock(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        started = asyncio.Event()

        async def collect():
            started.set()
            await asyncio.sleep(999)

        task = asyncio.create_task(run(
            book.engine, candidate=None, provider=PROVIDER, collect_bars=collect,
            poll_seconds=.01,
        ))
        await asyncio.wait_for(started.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert book.engine.drain_requested()
        assert not status(database)["running"]
        assert status(database)["phase"] == "INTERRUPTED"
        result = await run(
            book.engine, candidate=None, provider=PROVIDER, collect_bars=unavailable, max_cycles=1,
        )
        assert result["phase"] == "STOPPED"


@pytest.mark.asyncio
async def test_restart_with_different_strategy_does_not_abandon_existing_run(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        root = state_directory(database)
        root.mkdir()
        publish(root, "status.json", dict(
            run_id="previous", fingerprint="b" * 64, phase="INTERRUPTED",
            owned_symbols=1, pending_orders=0,
        ))
        with pytest.raises(ValueError, match="STRATEGY_RESTART_MISMATCH"):
            await run(book.engine, candidate=None, provider=PROVIDER, collect_bars=unavailable)
        assert not status(database)["running"]
        assert book.requests == []


@pytest.mark.asyncio
async def test_external_stop_is_checked_at_the_last_broker_boundary(tmp_path):
    from contextlib import asynccontextmanager

    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        candidate, bars = signals(book)
        original = book.engine.router.execution_authority.account_lock

        @asynccontextmanager
        async def stop_at_lock(context):
            async with original(context):
                assert request_stop(database)["phase"] == "STOP_REQUESTED"
                yield

        book.engine.router.execution_authority.account_lock = stop_at_lock

        async def collect():
            return bars

        result = await run(
            book.engine, candidate=candidate, provider=PROVIDER, collect_bars=collect,
            poll_seconds=.01, max_cycles=5,
        )
        assert result["phase"] == "STOPPED"
        assert book.requests == []
        assert not result["entries_enabled"]


@pytest.mark.asyncio
async def test_real_cli_controls_same_execution_runtime(tmp_path):
    database = tmp_path / "test.db"
    script = Path(__file__).resolve().parents[2] / "scripts/intraday_operator.py"
    async with rehearsal_session(database) as book:
        started = asyncio.Event()

        async def collect():
            started.set()
            await asyncio.sleep(999)

        task = asyncio.create_task(run(
            book.engine, candidate=None, provider=PROVIDER, collect_bars=collect,
            poll_seconds=.01,
        ))
        try:
            await asyncio.wait_for(started.wait(), 3)
            for command in ("execution-status", "execution-stop"):
                process = await asyncio.create_subprocess_exec(
                    sys.executable, str(script), command, "--db", str(database),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                output, error = await asyncio.wait_for(process.communicate(), 10)
                assert process.returncode == 0, error.decode()
                result = json.loads(output)
                if command == "execution-status":
                    assert result["running"]
                    assert result["mode"] == "KIS_EXECUTION"
                else:
                    assert result["phase"] == "STOP_REQUESTED"
            assert (await asyncio.wait_for(task, 3))["phase"] == "STOPPED"
            assert book.requests == []
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task


@pytest.mark.asyncio
async def test_runtime_drain_preserves_external_holdings(tmp_path):
    from auto_invest.reconciliation.external_holdings import load_external_holdings

    database = tmp_path / "test.db"
    baseline_file = tmp_path / "holdings.toml"
    baseline_file.write_text('[[holdings]]\nsymbol = "SPY"\nqty = 4\n')
    async with rehearsal_session(database) as book:
        observe = book.observe

        async def existing():
            value = await observe()
            positions = dict(value.positions)
            positions["SPY"] = positions.get("SPY", 0) + 4
            return replace(
                value, positions=positions, sellable_positions=dict(positions),
                nav=value.nav + 4 * book.mark,
            )

        book.engine = IntradayExecutor(
            book.engine.router, fingerprint=FINGERPRINT, observe=existing,
            external_holdings=load_external_holdings(baseline_file),
            authority_guard=lambda: None, capital_limit=book.initial_cash, now=lambda: book.now,
        )
        await book.engine.step(book.decision(5))
        book.fill("1", 3, "100", terminal=True)
        book.engine.request_drain()
        task = asyncio.create_task(run(
            book.engine, candidate=None, provider=PROVIDER, collect_bars=unavailable,
            poll_seconds=.01,
        ))
        try:
            await wait_until(lambda: len(book.orders) == 2)
            assert book.orders["2"]["qty"] == 3
            book.fill("2", 3, "100")
            assert (await asyncio.wait_for(task, 3))["phase"] == "STOPPED"
            assert (await existing()).positions == {"SPY": 4}
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task


@pytest.mark.asyncio
async def test_hardlinked_database_cannot_create_an_independent_runtime_lock(tmp_path):
    database = tmp_path / "test.db"
    async with rehearsal_session(database) as book:
        os.link(database, tmp_path / "alias.db")
        with pytest.raises(ValueError, match="DATABASE_HARDLINK_UNSUPPORTED"):
            await run(book.engine, candidate=None, provider=PROVIDER, collect_bars=unavailable)
        assert book.requests == []
        assert not state_directory(database).exists()
