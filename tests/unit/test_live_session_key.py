"""XNYS regular-session key used by the production daily order claim."""

from __future__ import annotations

from datetime import UTC, datetime

from auto_invest.execution.live_session import open_xnys_session_key


def test_open_session_returns_new_york_trading_date() -> None:
    assert (
        open_xnys_session_key(datetime(2026, 8, 31, 14, 17, tzinfo=UTC))
        == "2026-08-31"
    )


def test_closed_or_holiday_session_returns_none() -> None:
    assert open_xnys_session_key(datetime(2026, 8, 31, 22, 17, tzinfo=UTC)) is None
    assert open_xnys_session_key(datetime(2026, 9, 7, 14, 17, tzinfo=UTC)) is None


def test_early_close_session_rejects_the_last_scheduled_retry() -> None:
    assert (
        open_xnys_session_key(datetime(2026, 11, 27, 17, 17, tzinfo=UTC))
        == "2026-11-27"
    )
    assert open_xnys_session_key(datetime(2026, 11, 27, 18, 17, tzinfo=UTC)) is None
