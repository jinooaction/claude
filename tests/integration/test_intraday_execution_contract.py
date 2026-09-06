"""KIS wire and durable execution contracts, with no external connection."""

from decimal import Decimal

import httpx
import pytest

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.diagnostics import KisOrderError
from auto_invest.broker.overseas import cancel_order
from auto_invest.execution.intraday import IntradayExecutor
from auto_invest.execution.intraday_rehearsal import FINGERPRINT, rehearsal_session, rehearse


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"rt_cd": "1", "msg1": "rejected"},
        {"output": {}},
        {"rt_cd": "0"},
    ],
)
async def test_cancel_requires_explicit_acceptance(response):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(
        base_url="https://kis.invalid", transport=httpx.MockTransport(handle)
    ) as http:
        client = ResilientClient(
            http,
            max_retries=3,
            rate_limiter=AsyncTokenBucket(100, 100),
            breaker=CircuitBreaker(3, 10),
        )
        with pytest.raises(KisOrderError):
            await cancel_order(
                client,
                access_token="test",
                app_key="test",
                app_secret="test",
                account="1234567801",
                kis_order_id="1",
                market="AMEX",
                symbol="SPY",
                qty=2,
            )
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cancel_wire_and_no_transport_retry():
    import json

    calls = []

    def handle(request):
        calls.append(json.loads(request.content))
        raise httpx.ReadTimeout("response lost", request=request)

    async with httpx.AsyncClient(
        base_url="https://kis.invalid", transport=httpx.MockTransport(handle)
    ) as http:
        client = ResilientClient(
            http,
            max_retries=3,
            rate_limiter=AsyncTokenBucket(100, 100),
            breaker=CircuitBreaker(3, 10),
        )
        with pytest.raises(KisOrderError):
            await cancel_order(
                client,
                access_token="test",
                app_key="test",
                app_secret="test",
                account="1234567801",
                kis_order_id="1",
                market="AMEX",
                symbol="SPY",
                qty=2,
            )
    assert len(calls) == 1
    assert calls[0]["PDNO"] == "SPY"
    assert calls[0]["ORD_QTY"] == "2"
    assert calls[0]["ORD_SVR_DVSN_CD"] == "0"
    assert calls[0]["OVRS_EXCG_CD"] == "AMEX"


@pytest.mark.asyncio
async def test_real_contract_round_trip_offline():
    result = await rehearse()
    assert result["simulated_broker_requests"] == 3
    assert result["final_owned_positions"] == {}
    assert result["orders_submitted"] == 0


@pytest.mark.asyncio
async def test_default_authorization_blocks_every_broker_request(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        engine = IntradayExecutor(
            book.engine.router, fingerprint=FINGERPRINT, observe=book.observe, now=lambda: book.now
        )
        assert (await engine.step(book.decision(5)))["status"] == "DENIED"
        assert book.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["cancel_timeout", "cancel_reject"])
async def test_uncertain_cancel_never_retries_or_discards_late_fill(tmp_path, failure):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        setattr(book, failure, True)
        result = await book.engine.step(book.decision(0))
        assert result["actions"][0]["result"] == "UNCERTAIN"
        for _ in range(3):
            await book.engine.step(book.decision(0))
        assert len(book.requests) == 2
        assert book.conn.execute("SELECT state FROM orders").fetchone()[0] == "SUBMITTED"
        book.fill("1", 2, "99", terminal=True)
        result = await book.engine.step(book.decision(0))
        assert result["actions"][0]["kind"] == "SUBMITTED"
        assert book.orders["2"]["qty"] == 2


@pytest.mark.asyncio
async def test_repeated_signal_and_restart_do_not_resubmit(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 5, "100")
        await book.engine.step(book.decision(5))
        engine = IntradayExecutor(
            book.engine.router,
            fingerprint=FINGERPRINT,
            observe=book.observe,
            authority_guard=lambda: None,
            capital_limit=Decimal("10000"),
            now=lambda: book.now,
        )
        for _ in range(3):
            assert (await engine.step(book.decision(5)))["actions"] == []
        assert len(book.requests) == 1


@pytest.mark.asyncio
async def test_crash_after_claim_never_replays_submission(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:

        async def die(**kwargs):
            raise SystemExit("simulated abrupt process death")

        original = book.engine.router.submit_order
        book.engine.router.submit_order = die
        with pytest.raises(SystemExit):
            await book.engine.step(book.decision(5))
        book.engine.router.submit_order = original
        result = await book.engine.step(book.decision(5))
        assert result["actions"][0]["kind"] == "DUPLICATE_OR_PENDING"
        assert not book.requests


@pytest.mark.asyncio
async def test_transport_loss_blocks_new_orders(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        book.submit_timeout = True
        first = await book.engine.step(book.decision(5))
        assert first["actions"][0]["kind"] == "SUBMISSION_UNKNOWN"
        # A matching price/quantity and unverified order time cannot prove identity.
        second = await book.engine.step(book.decision(5))
        assert second["status"] == "HALTED"
        assert len(book.requests) == 1


@pytest.mark.asyncio
async def test_stale_sell_requests_cancel_and_uses_observed_fill_time(tmp_path):
    from datetime import timedelta

    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 5, "99")
        book.now += timedelta(minutes=5)
        observed = book.now
        await book.engine.step(book.decision(0))
        stamp = book.engine.conn.execute("SELECT executed_at_utc FROM fills").fetchone()[0]
        from datetime import datetime

        assert datetime.fromisoformat(stamp.replace("Z", "+00:00")) == observed
        book.now += timedelta(minutes=5)
        result = await book.engine.step(book.decision(0))
        assert result["actions"][0]["kind"] == "CANCEL_REQUEST"
        assert book.requests[-1][1]["ORGN_ODNO"] == "2"


@pytest.mark.asyncio
async def test_cancel_rechecks_guard_inside_authority_before_claim(tmp_path):
    from auto_invest.execution.cancellation import request_cancellation

    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        corr = book.engine.conn.execute("SELECT correlation_id FROM orders").fetchone()[0]
        result = await request_cancellation(
            book.engine.router.execution_authority,
            correlation_id=corr,
            market="AMEX",
            reason="test",
            before_write_guard=lambda: "STALE_ACCOUNT",
        )
        assert result == "DEFERRED_BEFORE_WRITE" and len(book.requests) == 1
        assert not book.engine.conn.execute(
            "SELECT 1 FROM audit_log WHERE event_type='ORDER_CANCEL_REQUEST'"
        ).fetchone()


@pytest.mark.asyncio
async def test_close_cancels_buy_then_liquidates_only_confirmed_shares(tmp_path):
    from datetime import timedelta

    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 2, "100")
        book.now = book.now.replace(hour=19, minute=45)
        result = await book.engine.step(book.decision(5))
        assert result["actions"][0]["kind"] == "CANCEL_REQUEST"
        book.fill("1", 3, "100", terminal=True)
        book.now += timedelta(seconds=1)
        result = await book.engine.step(book.decision(5))
        assert result["actions"][0]["kind"] == "SUBMITTED"
        assert book.orders["2"]["sll_buy_dvsn_cd"] == "01"
        assert book.orders["2"]["qty"] == 3
        assert Decimal(book.orders["2"]["ft_ord_unpr3"]) == Decimal("99.94")


@pytest.mark.asyncio
async def test_position_mismatch_and_exposure_cap(tmp_path):
    from dataclasses import replace

    async with rehearsal_session(tmp_path / "test.db") as book:
        result = await book.engine.step(book.decision(21))
        assert result["actions"][0]["reason"] == "CASH_OR_EXPOSURE"
        observed = await book.observe()

        async def wrong():
            return replace(observed, positions={"SPY": 1})

        book.engine.observe = wrong
        result = await book.engine.step(book.decision(5))
        assert result["reason"] == "POSITION_RECONCILIATION_MISMATCH"
        assert book.requests == []


@pytest.mark.asyncio
async def test_simultaneous_step_uses_one_durable_claim(tmp_path):
    import asyncio

    async with rehearsal_session(tmp_path / "test.db") as book:
        results = await asyncio.gather(*(book.engine.step(book.decision(5)) for _ in range(5)))
        assert len(book.requests) == 1
        assert any(r["status"] in {"BUSY", "WAIT_BROKER"} for r in results)


@pytest.mark.asyncio
async def test_guard_rechecked_after_account_observation(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        count = 0

        async def delayed():
            nonlocal count
            result = await book.observe()
            count += 1
            if count == 2:
                book.now = book.now.replace(hour=19, minute=45)
            return result

        book.engine.observe = delayed
        result = await book.engine.step(book.decision(5))
        assert result["status"] == "HALTED" or result["actions"][0]["kind"] == "REJECTED_BY_GATE"
        assert not book.requests


@pytest.mark.asyncio
async def test_partial_fill_cash_is_cumulative_not_average_delta(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 2, "99")
        await book.engine.step(book.decision(5))
        book.fill("1", 3, "99.30")
        await book.engine.step(book.decision(5))
        fills = list(book.conn.execute("SELECT qty,price_usd FROM fills"))
        assert sum(row["qty"] * Decimal(row["price_usd"]) for row in fills) == Decimal("297.90")


@pytest.mark.asyncio
async def test_close_residual_retry_keeps_first_limit(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        book.fill("1", 5, "100")
        book.now = book.now.replace(hour=19, minute=45)
        await book.engine.step(book.decision(5))
        first_limit = book.orders["2"]["ft_ord_unpr3"]
        book.fill("2", 2, "100", terminal=True)
        book.mark = Decimal("95")
        result = await book.engine.step(book.decision(5))
        assert result["actions"][0]["kind"] == "SUBMITTED", result
        assert book.orders["3"]["qty"] == 3
        assert book.orders["3"]["ft_ord_unpr3"] == first_limit
        # Partial/terminal confirmation is necessary for the next request.
        await book.engine.step(book.decision(5))
        assert len(book.orders) == 3


@pytest.mark.asyncio
async def test_loss_halt_survives_recovery_and_does_not_reenter(tmp_path):
    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(20))
        book.fill("1", 20, "100")
        book.mark = Decimal("80")
        result = await book.engine.step(book.decision(20))
        assert result["status"] == "EXIT_ONLY", result
        assert book.orders["2"]["qty"] == 20
        book.fill("2", 20, "80")
        book.mark = Decimal("100")
        result = await book.engine.step(book.decision(20))
        assert result["status"] == "EXIT_ONLY"
        assert len(book.orders) == 2


@pytest.mark.asyncio
async def test_non_session_and_future_input_do_not_write(tmp_path):
    from datetime import timedelta

    async with rehearsal_session(tmp_path / "test.db") as book:
        result = await book.engine.step(book.decision(5, end=book.now + timedelta(minutes=5)))
        assert result["reason"] == "STALE_SIGNAL"
        book.now = book.now.replace(day=7)
        result = await book.engine.step(book.decision(5))
        assert result["status"] == "WAIT_SESSION"
        assert book.requests == []


@pytest.mark.asyncio
async def test_claim_and_event_records_cannot_be_rewritten(tmp_path):
    import sqlite3

    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        for table in ["intraday_execution_claims", "intraday_execution_events"]:
            with pytest.raises(sqlite3.IntegrityError):
                book.conn.execute(f"DELETE FROM {table}")
            with pytest.raises(sqlite3.IntegrityError):
                book.conn.execute(f"UPDATE {table} SET payload='{{}}'")


@pytest.mark.asyncio
async def test_preregistered_bar_signal_reaches_kis_router(tmp_path):
    from datetime import timedelta
    from pathlib import Path

    from auto_invest.analytics.intraday_paper_challenger import (
        build_candidate_registry,
        load_preregistration,
    )
    from auto_invest.execution.intraday_signals import execution_fingerprint
    from auto_invest.market_data.intraday import SYMBOLS, iso

    candidate = build_candidate_registry(
        load_preregistration(
            Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
        )
    )[0]
    provider = "kis-nasdaq-partial-unadjusted"
    async with rehearsal_session(tmp_path / "test.db") as book:
        opening = book.now.replace(hour=13, minute=30)
        book.now = opening + timedelta(minutes=45)
        bars = [
            dict(
                symbol=s,
                timestamp_utc=iso(opening + timedelta(minutes=5 * n)),
                open=100 + n,
                high=102 + n,
                low=99 + n,
                close=101 + n,
                volume=100000,
            )
            for n in range(9)
            for s in SYMBOLS
        ]
        book.mark = Decimal("109")
        engine = IntradayExecutor(
            book.engine.router,
            fingerprint=execution_fingerprint(candidate, provider),
            observe=book.observe,
            authority_guard=lambda: None,
            capital_limit=Decimal("10000"),
            now=lambda: book.now,
        )
        result = await engine.on_bars(candidate, provider=provider, bars=bars)
        assert result["status"] == "WAIT_BROKER", result
        assert len(book.orders) == 1
        request = book.requests[0][1]
        assert request["ORD_DVSN"] == "00"
        assert int(request["ORD_QTY"]) == 14


def test_cli_has_no_live_option_and_reports_offline_evidence():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/intraday_execution.py", "rehearse"],
        text=True,
        capture_output=True,
        check=True,
    )
    import json

    report = json.loads(result.stdout)
    assert report["mode"] == "offline_rehearsal"
    assert report["orders_submitted"] == 0
    result = subprocess.run(
        [sys.executable, "scripts/intraday_execution.py", "rehearse", "--live"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2


@pytest.mark.asyncio
async def test_prewrite_contention_does_not_consume_cancel(tmp_path):
    from datetime import timedelta

    from auto_invest.execution.cancellation import request_cancellation

    async with rehearsal_session(tmp_path / "test.db") as book:
        await book.engine.step(book.decision(5))
        row = book.conn.execute("SELECT correlation_id FROM orders").fetchone()
        authority = book.engine.router.execution_authority
        authority.lock_timeout_seconds = 0
        book.conn.execute(
            "INSERT INTO execution_authority_locks VALUES(?,?,?,?,?)",
            (
                authority.account_no,
                "another-worker",
                "test",
                book.now.isoformat(),
                (book.now + timedelta(minutes=2)).isoformat(),
            ),
        )
        result = await request_cancellation(
            authority, correlation_id=row[0], market="AMEX", reason="test"
        )
        assert result == "DEFERRED_BEFORE_WRITE"
        assert (
            book.conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE event_type='ORDER_CANCEL_REQUEST'"
            ).fetchone()[0]
            == 0
        )
        book.conn.execute("DELETE FROM execution_authority_locks WHERE owner='another-worker'")
        result = await request_cancellation(
            authority, correlation_id=row[0], market="AMEX", reason="test"
        )
        assert result == "ACKNOWLEDGED"
        assert len(book.requests) == 2
