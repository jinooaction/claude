"""Tests for `auto_invest.market_data.store` (T033)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.market_data.store import (
    PriceBar,
    get_bars,
    get_latest_bar,
    insert_bar,
)
from auto_invest.persistence import db


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _bar(
    *,
    symbol: str = "AAPL",
    timeframe: str = "1d",
    bar_open: str = "2026-05-02T00:00:00.000Z",
    open_p: str = "180",
    high: str = "182",
    low: str = "179",
    close: str = "181",
    volume: int = 1_000_000,
) -> PriceBar:
    return PriceBar(
        symbol=symbol,
        timeframe=timeframe,
        bar_open_utc=bar_open,
        open_usd=Decimal(open_p),
        high_usd=Decimal(high),
        low_usd=Decimal(low),
        close_usd=Decimal(close),
        volume=volume,
    )


def test_insert_bar_returns_true_on_first_insert(conn):
    assert insert_bar(conn, _bar()) is True


def test_insert_bar_returns_false_on_duplicate_key(conn):
    insert_bar(conn, _bar())
    # Same (symbol, timeframe, bar_open_utc) — different OHLC values.
    assert insert_bar(conn, _bar(close="999")) is False


def test_first_write_wins_on_duplicate(conn):
    insert_bar(conn, _bar(close="100"))
    insert_bar(conn, _bar(close="200"))
    [bar] = get_bars(conn, symbol="AAPL", timeframe="1d")
    assert bar.close_usd == Decimal("100")


def test_get_bars_returns_in_ascending_order(conn):
    for ts in ["2026-05-03T00:00:00.000Z", "2026-05-01T00:00:00.000Z", "2026-05-02T00:00:00.000Z"]:
        insert_bar(conn, _bar(bar_open=ts))
    bars = get_bars(conn, symbol="AAPL", timeframe="1d")
    assert [b.bar_open_utc for b in bars] == [
        "2026-05-01T00:00:00.000Z",
        "2026-05-02T00:00:00.000Z",
        "2026-05-03T00:00:00.000Z",
    ]


def test_get_bars_filters_by_symbol_and_timeframe(conn):
    insert_bar(conn, _bar(symbol="AAPL", timeframe="1d"))
    insert_bar(conn, _bar(symbol="MSFT", timeframe="1d"))
    insert_bar(conn, _bar(symbol="AAPL", timeframe="1h", bar_open="2026-05-02T13:00:00.000Z"))

    aapl_daily = get_bars(conn, symbol="AAPL", timeframe="1d")
    assert len(aapl_daily) == 1


def test_get_bars_since_filter(conn):
    for day in ("01", "02", "03"):
        insert_bar(conn, _bar(bar_open=f"2026-05-{day}T00:00:00.000Z"))
    bars = get_bars(
        conn,
        symbol="AAPL",
        timeframe="1d",
        since_utc="2026-05-02T00:00:00.000Z",
    )
    assert [b.bar_open_utc for b in bars] == [
        "2026-05-02T00:00:00.000Z",
        "2026-05-03T00:00:00.000Z",
    ]


def test_get_bars_limit(conn):
    for day in ("01", "02", "03"):
        insert_bar(conn, _bar(bar_open=f"2026-05-{day}T00:00:00.000Z"))
    bars = get_bars(conn, symbol="AAPL", timeframe="1d", limit=2)
    assert len(bars) == 2


def test_get_latest_bar_returns_most_recent(conn):
    for day in ("01", "02", "03"):
        insert_bar(conn, _bar(bar_open=f"2026-05-{day}T00:00:00.000Z", close=f"18{day}"))
    latest = get_latest_bar(conn, symbol="AAPL", timeframe="1d")
    assert latest is not None
    assert latest.bar_open_utc == "2026-05-03T00:00:00.000Z"


def test_get_latest_bar_returns_none_when_empty(conn):
    assert get_latest_bar(conn, symbol="AAPL", timeframe="1d") is None
