"""Deterministic clock + wall-clock leak guard for the backtest engine.

FR-B02: a replay run MUST NOT call the system clock from any auto_invest
production code path. The guard works by monkey-patching `datetime.now`
and `time.time` inside the `auto_invest.*` module namespaces during the
guarded scope and raising `WallClockLeakError` on any read.

See research.md R-B1 (clock injection) and R-B2 (leak detection).
"""

from __future__ import annotations

import datetime as _datetime_mod
import sys
import time as _time_mod
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class WallClockLeakError(RuntimeError):
    """Raised when production code reads the wall clock during a backtest."""


class Clock(Protocol):
    """The injection seam every backtest-touched code path must accept."""

    def now(self) -> datetime: ...
    def utcnow_iso_ms(self) -> str: ...


@dataclass
class ReplayClock:
    """Deterministic clock; advance_to is the only way time moves."""

    current: datetime

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        self.current = start.astimezone(UTC)

    def now(self) -> datetime:
        return self.current

    def advance_to(self, ts: datetime) -> None:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        ts = ts.astimezone(UTC)
        if ts < self.current:
            raise ValueError(f"clock cannot rewind: {self.current} -> {ts}")
        self.current = ts

    def utcnow_iso_ms(self) -> str:
        now = self.current
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _all_auto_invest_modules() -> Iterable[object]:
    """Iterate over every loaded module rooted at `auto_invest.*` plus root."""
    for name, mod in list(sys.modules.items()):
        if (name == "auto_invest" or name.startswith("auto_invest.")) and mod is not None:
            yield mod


class _LeakyDateTime(_datetime_mod.datetime):
    """Replacement for `datetime.datetime` that raises on now/utcnow."""

    @classmethod
    def now(cls, tz=None):  # noqa: D401
        raise WallClockLeakError("datetime.now() called during backtest replay")

    @classmethod
    def utcnow(cls):  # noqa: D401
        raise WallClockLeakError("datetime.utcnow() called during backtest replay")


def _leaky_time() -> float:
    raise WallClockLeakError("time.time() called during backtest replay")


def _leaky_monotonic() -> float:
    raise WallClockLeakError("time.monotonic() called during backtest replay")


@contextmanager
def wall_clock_guard() -> Iterator[None]:
    """Activate WALL_CLOCK_LEAK detection for the duration of the scope.

    Patches `datetime.datetime`, `time.time`, and `time.monotonic` in every
    currently-loaded `auto_invest.*` module. Saves and restores originals
    so the live worker, run later in the same Python process, is unaffected.
    """
    targets: list[tuple[object, str, object]] = []  # (module, attr, original)

    # Snapshot before we patch so we know exactly what to restore.
    for mod in _all_auto_invest_modules():
        if hasattr(mod, "datetime"):
            attr = mod.datetime
            # The module's `datetime` is either the class or the module
            # itself (when imported as `import datetime`).
            if attr is _datetime_mod.datetime:
                targets.append((mod, "datetime", attr))
        if hasattr(mod, "time") and mod.time is _time_mod:
            targets.append((mod, "time", _time_mod))

    # Patch.
    patched_time_module = type(_time_mod)("time_guarded")
    patched_time_module.time = _leaky_time
    patched_time_module.monotonic = _leaky_monotonic
    # Re-export everything else from the original time module so any other
    # function the consumer relies on is still available.
    for attr_name in dir(_time_mod):
        if attr_name in ("time", "monotonic") or attr_name.startswith("_"):
            continue
        setattr(patched_time_module, attr_name, getattr(_time_mod, attr_name))

    for mod, attr, _orig in targets:
        if attr == "datetime":
            mod.datetime = _LeakyDateTime
        elif attr == "time":
            mod.time = patched_time_module

    try:
        yield
    finally:
        for mod, attr, orig in targets:
            setattr(mod, attr, orig)


__all__ = [
    "Clock",
    "ReplayClock",
    "WallClockLeakError",
    "wall_clock_guard",
]
