"""Process lifecycle for the existing diagnostic paper runtime; no broker writes."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from auto_invest.market_data.intraday import DataError


def prepare_root(root: Path):
    if root.is_symlink():
        raise DataError("OPERATOR_ROOT_SYMLINK")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not root.is_dir():
        raise DataError("OPERATOR_ROOT_INVALID")


@contextmanager
def lock(root: Path, name: str, *, blocking=False):
    prepare_root(root)
    fd = os.open(root / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            acquired = True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def read(root: Path, name: str):
    path = root / name
    if path.is_symlink():
        raise DataError("OPERATOR_STATE_SYMLINK")
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 1_000_000:
            raise ValueError
        result = json.loads(path.read_text())
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (ValueError, OSError):
        raise DataError("OPERATOR_STATE_INVALID") from None


def publish(root: Path, name: str, value):
    if (root / name).is_symlink():
        raise DataError("OPERATOR_STATE_SYMLINK")
    temporary = root / ("." + name + "." + uuid4().hex)
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, root / name)
    finally:
        temporary.unlink(missing_ok=True)


def record_event(root: Path, state):
    fd = os.open(
        root / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(fd, "a") as handle:
        handle.write(json.dumps(state, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def status(root: Path):
    if not root.exists():
        return dict(phase="NOT_STARTED", running=False, mode="KIS_PAPER", orders_submitted=0)
    with (
        lock(root, "control.lock", blocking=True),
        lock(root, "operator.lock") as available,
    ):
        state = read(root, "status.json") or dict(phase="NOT_STARTED")
        state["running"] = not available
        if available and state["phase"] in {"RUNNING", "RETRY_WAIT", "STOP_REQUESTED"}:
            state["phase"] = "INTERRUPTED"
        state.update(mode="KIS_PAPER", orders_submitted=0)
        return state


def request_stop(root: Path):
    if not root.exists():
        return dict(phase="NOT_RUNNING", orders_submitted=0)
    with (
        lock(root, "control.lock", blocking=True),
        lock(root, "operator.lock") as available,
    ):
        state = read(root, "status.json")
        if available or not state or not state.get("run_id"):
            return dict(phase="NOT_RUNNING", orders_submitted=0)
        publish(root, "stop.json", dict(run_id=state["run_id"]))
        return dict(phase="STOP_REQUESTED", run_id=state["run_id"], orders_submitted=0)


async def run(root: Path, *, cycle, poll_seconds=60, cycles=0, stop_event=None):
    if type(cycles) is not int or not 0 <= cycles <= 10000 or not 60 <= poll_seconds <= 300:
        raise DataError("OPERATOR_RUN_BOUNDS")
    stop_event = stop_event or asyncio.Event()
    # Lock acquisition follows the same control -> process order as status/stop.
    # Release control before awaits so other processes can issue a stop request.
    with lock(root, "control.lock", blocking=True):
        owner = lock(root, "operator.lock")
        acquired = owner.__enter__()
        if not acquired:
            owner.__exit__(None, None, None)
            return dict(phase="ALREADY_RUNNING", orders_submitted=0)
        run_id = uuid4().hex
        state = dict(
            schema=184, run_id=run_id, phase="RUNNING", mode="KIS_PAPER",
            cycles_completed=0, consecutive_failures=0, orders_submitted=0,
            updated_at=datetime.now(UTC).isoformat(), last_result=None,
        )
        try:
            record_event(root, state)
            publish(root, "status.json", state)
        except BaseException:
            owner.__exit__(None, None, None)
            raise

    def stopping():
        return stop_event.is_set() or (read(root, "stop.json") or {}).get("run_id") == run_id

    def save(phase):
        state.update(phase=phase, updated_at=datetime.now(UTC).isoformat())
        record_event(root, state)
        publish(root, "status.json", state)

    try:
        while cycles == 0 or state["cycles_completed"] < cycles:
            if stopping():
                save("STOPPED")
                return state
            try:
                result = await cycle()
                if not isinstance(result, dict) or result.get("orders_submitted", 0) != 0:
                    raise DataError("UNEXPECTED_CYCLE_RESULT")
                state.update(last_result=result, consecutive_failures=0)
                state["cycles_completed"] += 1
                save("RUNNING")
            except Exception as exc:
                state["consecutive_failures"] += 1
                state["last_error"] = str(exc) if isinstance(exc, DataError) else "CYCLE_FAILED"
                save("RETRY_WAIT")
                if state["consecutive_failures"] >= 3:
                    save("FAILED")
                    return state
            if stopping():
                save("STOPPED")
                return state
            if cycles and state["cycles_completed"] >= cycles:
                break
            # Interruptible polling: no subprocess termination or PID reuse hazard.
            for _ in range(poll_seconds):
                if stopping():
                    break
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=1)
        save("COMPLETED")
        return state
    except asyncio.CancelledError:
        save("INTERRUPTED")
        raise
    except Exception:
        save("FAILED")
        raise
    finally:
        owner.__exit__(None, None, None)
