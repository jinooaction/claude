"""Persistent execution lifecycle; keeps order management independent of signal IO."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from auto_invest.analytics.intraday_operator import lock, publish, read, record_event
from auto_invest.execution.intraday import IntradayExecutor

ACTIVE = {"RUNNING", "STARTING", "MANAGING", "DRAINING", "WAIT_INPUT", "WAIT_SESSION", "BLOCKED"}


def _publish(root, name, value):
    publish(root, name, value)
    # Persist the rename and state-directory entry before acknowledging stop.
    for directory in (root, root.parent):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def state_directory(database: Path) -> Path:
    database = database.resolve()
    return database.parent / ("." + database.name + ".intraday-runtime")


def status(database: Path) -> dict:
    root = state_directory(database)
    if not root.exists():
        return dict(phase="NOT_STARTED", running=False, entries_enabled=False)
    with lock(root, "control.lock", blocking=True), lock(root, "runtime.lock") as available:
        state = read(root, "status.json") or dict(phase="NOT_STARTED")
        state["running"] = not available
        if available and state["phase"] in ACTIVE:
            state.update(phase="INTERRUPTED", entries_enabled=False)
        return state


def request_stop(database: Path) -> dict:
    root = state_directory(database)
    if not root.exists():
        return dict(phase="NOT_RUNNING")
    with lock(root, "control.lock", blocking=True), lock(root, "runtime.lock") as available:
        state = read(root, "status.json")
        if available or not state or not state.get("run_id"):
            return dict(phase="NOT_RUNNING")
        _publish(root, "stop.json", dict(run_id=state["run_id"]))
        return dict(phase="STOP_REQUESTED", run_id=state["run_id"])


async def run(
    engine: IntradayExecutor,
    *,
    candidate,
    provider: str,
    collect_bars,
    poll_seconds: float = 5,
    collection_seconds: float = 60,
    collection_timeout: float = 45,
    max_cycles: int = 0,
    stop_event: asyncio.Event | None = None,
) -> dict:
    """Use an already configured, authorized engine and the common trading DB.

    No credentials, authority, NAV or fills are invented here. A finite cycle
    bound is for callers that explicitly take over management after return.
    STOPPED requires fresh broker reconciliation of zero owned/open positions.
    """
    if (
        not 0.01 <= poll_seconds <= 30
        or not 0.01 <= collection_seconds <= 300
        or not 0.01 <= collection_timeout <= 60
        or type(max_cycles) is not int
        or not 0 <= max_cycles <= 10000
    ):
        raise ValueError("EXECUTION_RUNTIME_BOUNDS")
    database = Path(engine.conn.execute("PRAGMA database_list").fetchone()[2])
    if database.stat().st_nlink != 1:
        raise ValueError("DATABASE_HARDLINK_UNSUPPORTED")
    root = state_directory(database)
    stop_event = stop_event or asyncio.Event()
    with lock(root, "control.lock", blocking=True):
        owner = lock(root, "runtime.lock")
        acquired = owner.__enter__()
        if not acquired:
            owner.__exit__(None, None, None)
            return dict(phase="ALREADY_RUNNING", entries_enabled=False)
        try:
            prior = read(root, "status.json")
            if prior and prior.get("fingerprint") != engine.fingerprint and (
                prior.get("phase") != "STOPPED"
                or prior.get("owned_symbols") != 0
                or prior.get("pending_orders") != 0
            ):
                raise ValueError("STRATEGY_RESTART_MISMATCH")
            pending_stop = read(root, "stop.json")
            if (
                prior and prior.get("phase") != "STOPPED" and pending_stop
                and pending_stop.get("run_id") == prior.get("run_id")
            ):
                engine.request_drain()
            state = dict(
                schema=184,
                mode="KIS_EXECUTION",
                fingerprint=engine.fingerprint,
                run_id=uuid4().hex,
                phase="STARTING",
                cycles_completed=0,
                entries_enabled=False,
                last_result=None,
                signal_state="WAITING",
                **engine.management_state(),
            )
            record_event(root, state)
            _publish(root, "status.json", state)
        except BaseException:
            owner.__exit__(None, None, None)
            raise

    def stopping():
        return (
            stop_event.is_set()
            or (read(root, "stop.json") or {}).get("run_id") == state["run_id"]
            or engine.drain_requested()
        )

    def save(phase):
        state.update(
            phase=phase,
            updated_at=datetime.now(UTC).isoformat(),
            **engine.management_state(),
        )
        record_event(root, state)
        _publish(root, "status.json", state)

    source = dict(bars=None, generation=0, error=None)

    async def collect():
        while True:
            try:
                bars = await asyncio.wait_for(collect_bars(), collection_timeout)
                if not isinstance(bars, list) or not 1 <= len(bars) <= 10000:
                    raise ValueError
                source.update(bars=[dict(row) for row in bars], error=None)
                source["generation"] += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                source.update(bars=None, error="BAR_COLLECTION_FAILED")
            await asyncio.sleep(collection_seconds)

    previous_entry_guard = engine.entry_guard
    engine.entry_guard = lambda: (
        ("OPERATOR_STOP_REQUESTED" if stopping() else None) or previous_entry_guard()
    )
    collector = None
    consumed = 0
    try:
        while True:
            if stopping():
                engine.request_drain()
                if collector is not None:
                    collector.cancel()
                    with suppress(asyncio.CancelledError):
                        await collector
                    collector = None
            result = await engine.manage()
            state.update(
                last_result=result, entries_enabled=False,
                signal_state="UNAVAILABLE" if source["error"] else (
                    "AVAILABLE" if source["bars"] is not None else "WAITING"
                ),
            )
            state["cycles_completed"] += 1
            if result["status"] == "STOPPED":
                save("STOPPED")
                return state
            draining = stopping()
            if draining:
                engine.request_drain()
                phase = "DRAINING"
            elif result["status"] == "WAIT_SESSION":
                phase = "WAIT_SESSION"
            elif result["status"] in {"DENIED", "HALTED", "BUSY"}:
                phase = "BLOCKED"
            else:
                counts = engine.management_state()
                phase = "MANAGING" if counts["owned_symbols"] or counts["pending_orders"] else (
                    "WAIT_INPUT"
                )
                if collector is None:
                    collector = asyncio.create_task(collect())
                if source["bars"] is not None and source["generation"] > consumed:
                    consumed = source["generation"]
                    # A stop arriving during management is checked again here
                    # and by the engine at the broker's last write boundary.
                    if not stopping():
                        result = await engine.on_bars(
                            candidate, provider=provider, bars=source["bars"]
                        )
                        state["last_result"] = result
                        state["entries_enabled"] = (
                            result["status"] == "PROCESSED" and not stopping()
                        )
                        phase = {
                            "PROCESSED": "RUNNING", "WAIT_BROKER": "MANAGING",
                            "EXIT_ONLY": "DRAINING", "WAIT_SESSION": "WAIT_SESSION",
                        }.get(result["status"], "BLOCKED")
            save(phase)
            if max_cycles and state["cycles_completed"] >= max_cycles:
                state["entries_enabled"] = False
                save("NEEDS_ATTENTION" if (
                    state["owned_symbols"] or state["pending_orders"] or state["drain_requested"]
                    or result["status"] in {"DENIED", "HALTED", "BUSY"}
                ) else "PAUSED")
                return state
            # Once stopping, do not spin on an already-set event while waiting
            # for the broker to confirm cancels/fills.
            if stop_event.is_set():
                await asyncio.sleep(poll_seconds)
            else:
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), poll_seconds)
    except BaseException:
        engine.request_drain()
        state["entries_enabled"] = False
        save("INTERRUPTED")
        raise
    finally:
        try:
            if collector is not None:
                collector.cancel()
                with suppress(asyncio.CancelledError):
                    await collector
        finally:
            engine.entry_guard = previous_entry_guard
            owner.__exit__(None, None, None)
