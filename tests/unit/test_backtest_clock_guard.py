"""FR-B02 (wall-clock leak) safety-contract tests."""

from __future__ import annotations

import time as _time
from datetime import UTC, datetime

import pytest

from auto_invest.backtest.clock import (
    ReplayClock,
    WallClockLeakError,
    wall_clock_guard,
)


def test_replay_clock_advances_monotonically():
    rc = ReplayClock(datetime(2024, 1, 2, 14, 30, tzinfo=UTC))
    assert rc.now() == datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    rc.advance_to(datetime(2024, 1, 2, 21, 0, tzinfo=UTC))
    assert rc.now() == datetime(2024, 1, 2, 21, 0, tzinfo=UTC)


def test_replay_clock_rejects_rewind():
    rc = ReplayClock(datetime(2024, 1, 2, 21, 0, tzinfo=UTC))
    with pytest.raises(ValueError, match="cannot rewind"):
        rc.advance_to(datetime(2024, 1, 2, 14, 30, tzinfo=UTC))


def test_replay_clock_utcnow_iso_ms_matches_now():
    rc = ReplayClock(datetime(2024, 1, 2, 14, 30, 0, 123000, tzinfo=UTC))
    assert rc.utcnow_iso_ms() == "2024-01-02T14:30:00.123Z"


def test_replay_clock_normalises_naive_to_utc():
    rc = ReplayClock(datetime(2024, 1, 2, 14, 30))
    assert rc.now().tzinfo == UTC


def test_wall_clock_guard_raises_on_datetime_now_in_auto_invest_module():
    # Reach into a real auto_invest module that imports `datetime` and
    # call datetime.now() while guarded. It must raise.
    from auto_invest.persistence import audit as audit_mod

    with wall_clock_guard(), pytest.raises(WallClockLeakError):
        audit_mod.datetime.now(UTC)


def test_wall_clock_guard_raises_on_time_time_in_auto_invest_module():
    # Add a stub auto_invest module that imports `time` and tries to read it.
    from auto_invest.backtest import clock as guarded_mod

    # Inject a `time` attribute we can call through.
    guarded_mod.time = _time  # type: ignore[attr-defined]
    try:
        with wall_clock_guard(), pytest.raises(WallClockLeakError):
            guarded_mod.time.time()
    finally:
        if hasattr(guarded_mod, "time"):
            delattr(guarded_mod, "time")


def test_wall_clock_guard_does_not_leak_outside_scope():
    from auto_invest.persistence import audit as audit_mod

    with wall_clock_guard():
        pass
    # Outside the scope, datetime.now() works again.
    now = audit_mod.datetime.now(UTC)
    assert now.tzinfo == UTC


def test_wall_clock_guard_restores_originals_on_exception():
    from auto_invest.persistence import audit as audit_mod

    class _Boom(RuntimeError):
        pass

    try:
        with wall_clock_guard():
            raise _Boom()
    except _Boom:
        pass

    # Datetime must be restored even though the body raised.
    audit_mod.datetime.now(UTC)
