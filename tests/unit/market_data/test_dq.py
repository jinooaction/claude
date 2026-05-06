"""T019 — gap + vendor-disagreement detectors."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.market_data.adapters import BarRecord, InstrumentRef
from auto_invest.market_data.calendar import AlwaysOpenCalendar, get_calendar
from auto_invest.market_data.dq import detect_gaps, detect_vendor_disagreement
from auto_invest.market_data.historical_store import write_bars
from auto_invest.persistence import db


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


AAPL = InstrumentRef("equity", "nasdaq", "AAPL")


def _bar(day: int, close: Decimal, vendor: str = "kis") -> BarRecord:
    return BarRecord(
        instrument=AAPL,
        kind="ohlcv_1d",
        bar_open_ts_utc=datetime(2024, 6, day, tzinfo=timezone.utc),
        open=close, high=close + Decimal("1"), low=close - Decimal("1"),
        close=close, volume=Decimal("1000000"),
    )


def test_detect_gaps_marks_missing_session_days(conn: sqlite3.Connection) -> None:
    # 2024-06-03 (Mon) and 2024-06-05 (Wed) only — 06-04 (Tue) is missing.
    write_bars(conn, [_bar(3, Decimal("190"))], vendor="kis",
               as_of_ts=datetime(2024, 6, 6, tzinfo=timezone.utc))
    write_bars(conn, [_bar(5, Decimal("191"))], vendor="kis",
               as_of_ts=datetime(2024, 6, 6, tzinfo=timezone.utc))

    n = detect_gaps(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d", vendor="kis",
        calendar=get_calendar("nasdaq"),
        from_utc=datetime(2024, 6, 3, tzinfo=timezone.utc),
        to_utc=datetime(2024, 6, 6, tzinfo=timezone.utc),
    )
    # 2024-06-04 is a Tuesday session and is missing.
    assert n == 1
    rows = conn.execute("SELECT severity, payload_json FROM data_quality_events").fetchall()
    assert rows[0]["severity"] == "block"
    assert "2024-06-04" in rows[0]["payload_json"]


def test_detect_gaps_skips_weekends_for_discrete_calendar(conn: sqlite3.Connection) -> None:
    # Only Friday + Monday — gap detector for the weekend writes nothing.
    write_bars(conn, [_bar(7, Decimal("192")), _bar(10, Decimal("193"))],
               vendor="kis", as_of_ts=datetime(2024, 6, 11, tzinfo=timezone.utc))
    n = detect_gaps(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d", vendor="kis",
        calendar=get_calendar("nasdaq"),
        from_utc=datetime(2024, 6, 7, tzinfo=timezone.utc),
        to_utc=datetime(2024, 6, 11, tzinfo=timezone.utc),
    )
    assert n == 0


def test_detect_vendor_disagreement(conn: sqlite3.Connection) -> None:
    # Same bar from two vendors with prices 100 vs 101 (~99 bps).
    write_bars(conn, [_bar(3, Decimal("100"))], vendor="kis",
               as_of_ts=datetime(2024, 6, 4, tzinfo=timezone.utc))
    # craft a disagreeing vendor
    bar_b = BarRecord(
        instrument=AAPL, kind="ohlcv_1d",
        bar_open_ts_utc=datetime(2024, 6, 3, tzinfo=timezone.utc),
        open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
        close=Decimal("101"),  # 1% diff at close → 99 bps
        volume=Decimal("1000000"),
    )
    write_bars(conn, [bar_b], vendor="other",
               as_of_ts=datetime(2024, 6, 4, tzinfo=timezone.utc))

    # tolerance 50 bps → fires
    n = detect_vendor_disagreement(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d",
        tolerance_bps=Decimal("50"),
    )
    assert n == 1

    # tolerance 200 bps → does not fire
    n2 = detect_vendor_disagreement(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d",
        tolerance_bps=Decimal("200"),
    )
    assert n2 == 0


def test_always_open_gap_detector_includes_weekends(conn: sqlite3.Connection) -> None:
    # Crypto symbol; missing 2024-01-02
    btc = InstrumentRef("crypto", "binance", "BTC-USD")

    def _bar_btc(d: int, c: Decimal) -> BarRecord:
        return BarRecord(
            instrument=btc, kind="ohlcv_1d",
            bar_open_ts_utc=datetime(2024, 1, d, tzinfo=timezone.utc),
            open=c, high=c + Decimal("1"), low=c - Decimal("1"),
            close=c, volume=Decimal("100"),
        )

    write_bars(conn, [_bar_btc(1, Decimal("42000"))], vendor="crypto_public",
               as_of_ts=datetime(2024, 1, 4, tzinfo=timezone.utc))
    write_bars(conn, [_bar_btc(3, Decimal("42500"))], vendor="crypto_public",
               as_of_ts=datetime(2024, 1, 4, tzinfo=timezone.utc))

    n = detect_gaps(
        conn,
        asset_class="crypto", venue="binance", symbol="BTC-USD",
        kind="ohlcv_1d", vendor="crypto_public",
        calendar=AlwaysOpenCalendar(venue="binance"),
        from_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_utc=datetime(2024, 1, 4, tzinfo=timezone.utc),
    )
    assert n == 1
