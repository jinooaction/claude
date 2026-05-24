"""스펙 005 — 안전 게이트: 장 시간 + 측정 (SC-A06, SC-A07)."""

from __future__ import annotations

from datetime import UTC, datetime

from auto_invest.tuner.gates import market_hours_blocked, measurement_sufficient


def test_blocked_during_regular_session() -> None:
    # 2026-05-26 (화) 15:00 UTC — EDT 09:30~16:00 ET = 13:30~20:00 UTC, 장중.
    now = datetime(2026, 5, 26, 15, 0, tzinfo=UTC)
    assert market_hours_blocked(now) is True


def test_blocked_within_preopen_margin() -> None:
    # 13:15 UTC — 13:30 개장 15분 전(30분 마진 안).
    now = datetime(2026, 5, 26, 13, 15, tzinfo=UTC)
    assert market_hours_blocked(now) is True


def test_not_blocked_offhours_weekend() -> None:
    # 2026-05-30 (토) 12:00 UTC — 휴장, 다음 개장 월요일 → 마진 밖.
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)
    assert market_hours_blocked(now) is False


def test_not_blocked_late_evening_weekday() -> None:
    # 2026-05-26 (화) 23:00 UTC — 폐장(20:00 UTC) 후, 다음 개장 멀음.
    now = datetime(2026, 5, 26, 23, 0, tzinfo=UTC)
    assert market_hours_blocked(now) is False


def test_measurement_gate() -> None:
    assert measurement_sufficient(20, 20) is True
    assert measurement_sufficient(21, 20) is True
    assert measurement_sufficient(19, 20) is False
    assert measurement_sufficient(0, 20) is False
