import asyncio
import contextlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from websockets.asyncio.server import serve

from auto_invest.analytics.intraday_operator import (
    publish,
    read,
    request_stop,
    run,
    status,
)
from auto_invest.analytics.intraday_runtime import read_status
from auto_invest.broker.intraday_inputs import WS_URL, StrictQuoteFeed
from auto_invest.market_data.intraday import SYMBOLS, DataError, iso

NOW = datetime(2026, 9, 8, 14, 30, tzinfo=UTC)
TRADE = (
    "0|HDFSCNT0|001|DNASQQQ^QQQ^2^20260908^20260908^103000^20260908^233000^"
    "100^101^99^100.00^0^0^0^99.99^100.01^1^1^1^10000^1000000^0^0^100^1"
)


@pytest.mark.asyncio
async def test_real_websocket_transport_subscribes_receives_then_clears_on_disconnect(monkeypatch):
    release = asyncio.Event()
    seen = []

    async def server(socket):
        assert socket.request.path == "/tryitout"
        subscription = json.loads(await socket.recv())
        seen.append(subscription)
        await socket.send(json.dumps(dict(
            header=dict(tr_id="HDFSCNT0", tr_key="DNASQQQ"), body=dict(rt_cd="0"),
        )))
        await socket.send(TRADE)
        await release.wait()

    async def approval():
        return "offline-test-key"

    async with serve(server, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        monkeypatch.setattr(
            "auto_invest.broker.intraday_inputs.WS_URL",
            f"ws://127.0.0.1:{port}" + urlsplit(WS_URL).path,
        )
        feed = StrictQuoteFeed(("QQQ",), now=lambda: NOW)
        task = asyncio.create_task(feed.serve(approval=approval, attempts=1))
        try:
            async with asyncio.timeout(3):
                while not feed.snapshot():
                    await asyncio.sleep(.01)
            quote = feed.snapshot()["QQQ"]
            assert quote.source_at == NOW
            assert seen[0]["body"]["input"] == dict(tr_id="HDFSCNT0", tr_key="DNASQQQ")
            release.set()
            await asyncio.wait_for(task, 3)
            assert not feed.connected and not feed.snapshot()
            assert feed.reason == "QUOTE_TRANSPORT_FAILED"
        finally:
            release.set()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_process_lifecycle_stops_without_erasing_paper_state_and_restarts(tmp_path):
    started, release = asyncio.Event(), asyncio.Event()
    paper = tmp_path / "paper.db"
    paper.write_bytes(b"existing-paper-journal")

    async def cycle():
        started.set()
        await release.wait()
        return dict(status="WAIT_SESSION", orders_submitted=0)

    task = asyncio.create_task(run(tmp_path, cycle=cycle))
    await asyncio.wait_for(started.wait(), 1)
    first = status(tmp_path)
    assert first["running"]
    duplicate = await run(tmp_path, cycle=cycle, cycles=1)
    assert duplicate["phase"] == "ALREADY_RUNNING"
    assert request_stop(tmp_path)["run_id"] == first["run_id"]
    release.set()
    result = await asyncio.wait_for(task, 1)
    assert result["phase"] == "STOPPED"
    assert not status(tmp_path)["running"]
    restarted = await run(tmp_path, cycle=cycle, cycles=1)
    assert restarted["phase"] == "COMPLETED"
    assert restarted["run_id"] != first["run_id"]
    assert paper.read_bytes() == b"existing-paper-journal"
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert {event["run_id"] for event in events} == {first["run_id"], restarted["run_id"]}
    assert len(events) == 6


@pytest.mark.asyncio
async def test_stop_wakes_polling_without_an_extra_cycle(tmp_path):
    called = asyncio.Event()
    count = 0

    async def cycle():
        nonlocal count
        count += 1
        called.set()
        return dict(status="WAIT_SESSION")

    task = asyncio.create_task(run(tmp_path, cycle=cycle))
    await called.wait()
    request_stop(tmp_path)
    result = await asyncio.wait_for(task, 1.5)
    assert result["phase"] == "STOPPED"
    assert count == 1


@pytest.mark.asyncio
async def test_abrupt_cancellation_records_interrupted_and_releases_lock(tmp_path):
    started = asyncio.Event()

    async def cycle():
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(run(tmp_path, cycle=cycle))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert status(tmp_path)["phase"] == "INTERRUPTED"
    assert not status(tmp_path)["running"]


@pytest.mark.asyncio
async def test_failed_cycle_does_not_leak_exception_and_can_be_stopped(tmp_path):
    stop = asyncio.Event()

    async def cycle():
        stop.set()
        raise RuntimeError("secret-token-and-account")

    result = await run(tmp_path, cycle=cycle, stop_event=stop)
    assert result["phase"] == "STOPPED"
    assert result["last_error"] == "CYCLE_FAILED"
    assert "secret-token" not in (tmp_path / "events.jsonl").read_text()


def test_status_detects_dead_process_and_state_symlinks(tmp_path):
    publish(tmp_path, "status.json", dict(phase="RUNNING", run_id="old"))
    assert status(tmp_path)["phase"] == "INTERRUPTED"
    assert request_stop(tmp_path)["phase"] == "NOT_RUNNING"
    (tmp_path / "stop.json").symlink_to(tmp_path / "status.json")
    with pytest.raises(DataError, match="SYMLINK"):
        read(tmp_path, "stop.json")


def test_public_cli_help_status_and_missing_credentials(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KIS_", "APCA_"))}
    command = [sys.executable, "scripts/intraday_operator.py"]
    result = subprocess.run(command + ["--help"], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    assert "buying-power" in result.stdout and "quotes" in result.stdout
    result = subprocess.run(
        command + ["status", "--root", str(tmp_path / "new")],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["phase"] == "NOT_STARTED"
    assert not (tmp_path / "new").exists()
    result = subprocess.run(command + ["run"], capture_output=True, text=True, env=env)
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "KIS_CREDENTIALS_REQUIRED"
    assert "Traceback" not in result.stderr


@pytest.mark.asyncio
async def test_cli_run_is_bound_to_existing_runtime_not_a_new_dummy_loop(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("operator_cli", "scripts/intraday_operator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actual_execute = module.runtime_execute()
    assert Path(actual_execute.__code__.co_filename).name == "intraday_runtime.py"
    called = []

    async def existing(args):
        called.append(args)
        return dict(status="WAIT_SESSION", orders_submitted=0)

    monkeypatch.setattr(module, "runtime_execute", lambda: existing)
    monkeypatch.setenv("KIS_APP_KEY", "offline-key")
    monkeypatch.setenv("KIS_APP_SECRET", "offline-secret")
    args = module.parser().parse_args(["run", "--root", str(tmp_path), "--cycles", "1"])
    result = await module.execute(args)
    assert result["phase"] == "COMPLETED"
    assert len(called) == 1
    assert called[0].provider == "kis"
    assert called[0].state == tmp_path / "paper.db"
    assert called[0].out == tmp_path / "batches"


@pytest.mark.asyncio
async def test_operator_restarts_real_paper_runtime_without_duplicate_bars(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("operator_e2e", "scripts/intraday_operator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actual = module.runtime_execute()
    opening = datetime(2026, 9, 8, 13, 30, tzinfo=UTC)
    moment = opening + timedelta(minutes=5)
    rows = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    async def collect(*args, **kwargs):
        return dict(
            provider="kis-nasdaq-partial-unadjusted", bars=list(rows), pages=[], synthetic=False,
        )

    async def forbid_network(*args, **kwargs):
        raise AssertionError("offline fixtures must not reach a broker")

    monkeypatch.setitem(actual.__globals__, "datetime", Clock)
    monkeypatch.setitem(actual.__globals__, "_collect", collect)
    monkeypatch.setattr("httpx.AsyncClient.request", forbid_network)
    monkeypatch.setattr(module, "runtime_execute", lambda: actual)
    monkeypatch.setenv("KIS_APP_KEY", "offline")
    monkeypatch.setenv("KIS_APP_SECRET", "offline")
    args = module.parser().parse_args(["run", "--root", str(tmp_path), "--cycles", "1"])
    for n in range(20):
        stamp = opening + timedelta(minutes=5 * n)
        moment = stamp + timedelta(minutes=5)
        rows.extend(dict(
            symbol=s, timestamp_utc=iso(stamp), open=100 + n, high=102 + n,
            low=99 + n, close=100.5 + n, volume=100000,
        ) for s in SYMBOLS)
        result = await module.execute(args)
        assert result["phase"] == "COMPLETED"
    before = read_status(tmp_path / "paper.db")
    assert before["processed_bars"] == 20
    assert before["simulated_fills"] > 0
    assert len(before["accounts"]) == 18
    await module.execute(args)
    assert read_status(tmp_path / "paper.db") == before
    assert before["orders_submitted"] == 0
