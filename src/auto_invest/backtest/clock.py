"""Deterministic clock for replay.

The live worker reads time via `Worker.tick(now=datetime.now(UTC))` (the
default) or via the optional `clock` kwarg added in T013. The backtest
engine drives a `SyntheticClock` forward bar-by-bar so `Worker.tick` and
`worker/schedule.is_session_open` consume the same synthesised `now`,
without modifying K6 (`worker/schedule.py`).
"""

from __future__ import annotations

from datetime import UTC, datetime


class SyntheticClock:
    """Mutable container holding a single UTC datetime.

    Frozen-time within a single `Worker.tick`: the engine calls
    `advance_to(...)` between ticks, never inside one.
    """

    __slots__ = ("_now",)

    def __init__(self, start: datetime) -> None:
        self._now = self._normalise(start)

    @staticmethod
    def _normalise(dt: datetime) -> datetime:
        """Naive datetimes are forbidden; aware-non-UTC is converted to UTC."""
        if dt.tzinfo is None:
            raise ValueError("SyntheticClock requires a timezone-aware datetime")
        return dt.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def advance_to(self, dt: datetime) -> None:
        new = self._normalise(dt)
        if new < self._now:
            raise ValueError(f"SyntheticClock cannot run backwards: {new!r} < {self._now!r}")
        self._now = new

    def __call__(self) -> datetime:
        # Convenience: SyntheticClock is callable, satisfying
        # the `clock: Callable[[], datetime] | None` shape on Worker.__init__.
        return self._now
