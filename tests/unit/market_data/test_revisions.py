"""T018 — point-in-time barrier in the revisions reader (FR-B-002)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.market_data.adapters import (
    BarRecord,
    CorporateActionRecord,
    EventRecord,
    InstrumentRef,
)
from auto_invest.market_data.historical_store import (
    write_bars,
    write_corporate_actions,
    write_events,
)
from auto_invest.market_data.revisions import (
    iter_bars,
    iter_corporate_actions,
    iter_events,
    latest_as_of,
)
from auto_invest.persistence import db


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


AAPL = InstrumentRef("equity", "nasdaq", "AAPL")


def _bar(day: int, close: Decimal, *, vol: Decimal = Decimal("1000000")) -> BarRecord:
    return BarRecord(
        instrument=AAPL,
        kind="ohlcv_1d",
        bar_open_ts_utc=datetime(2024, 1, day, tzinfo=timezone.utc),
        open=close - Decimal("0.5"),
        high=close + Decimal("1"),
        low=close - Decimal("1"),
        close=close,
        volume=vol,
    )


def test_pin_returns_only_revisions_at_or_before_pin(conn: sqlite3.Connection) -> None:
    # Bar for 2024-01-02 written initially on 2024-01-02; revised on 2024-06-01.
    write_bars(conn, [_bar(2, Decimal("180"))], vendor="kis",
               as_of_ts=datetime(2024, 1, 2, tzinfo=timezone.utc))
    write_bars(conn, [_bar(2, Decimal("181.5"))], vendor="kis",
               as_of_ts=datetime(2024, 6, 1, tzinfo=timezone.utc))

    # Pin BEFORE the revision: see the original close.
    bars_before = list(iter_bars(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d", vendor="kis",
        from_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_utc=datetime(2024, 1, 31, tzinfo=timezone.utc),
        as_of_ts_pin=datetime(2024, 5, 31, tzinfo=timezone.utc),
    ))
    assert len(bars_before) == 1
    assert bars_before[0].close == Decimal("180")

    # Pin AFTER the revision: see the corrected close.
    bars_after = list(iter_bars(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d", vendor="kis",
        from_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_utc=datetime(2024, 1, 31, tzinfo=timezone.utc),
        as_of_ts_pin=datetime(2024, 7, 1, tzinfo=timezone.utc),
    ))
    assert len(bars_after) == 1
    assert bars_after[0].close == Decimal("181.5")


def test_window_filter_is_half_open(conn: sqlite3.Connection) -> None:
    write_bars(
        conn,
        [_bar(d, Decimal(f"{180+d}")) for d in range(2, 6)],
        vendor="kis",
        as_of_ts=datetime(2024, 1, 6, tzinfo=timezone.utc),
    )
    bars = list(iter_bars(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d", vendor="kis",
        from_utc=datetime(2024, 1, 3, tzinfo=timezone.utc),
        to_utc=datetime(2024, 1, 5, tzinfo=timezone.utc),
        as_of_ts_pin=datetime(2024, 6, 1, tzinfo=timezone.utc),
    ))
    # 2024-01-03, 2024-01-04 included; 2024-01-05 excluded (half-open).
    assert [b.bar_open_ts_utc for b in bars] == [
        "2024-01-03T00:00:00.000Z",
        "2024-01-04T00:00:00.000Z",
    ]


def test_idempotent_writes(conn: sqlite3.Connection) -> None:
    inserted_1 = write_bars(conn, [_bar(2, Decimal("180"))], vendor="kis",
                            as_of_ts=datetime(2024, 1, 2, tzinfo=timezone.utc))
    inserted_2 = write_bars(conn, [_bar(2, Decimal("180"))], vendor="kis",
                            as_of_ts=datetime(2024, 1, 2, tzinfo=timezone.utc))
    assert inserted_1 == 1
    assert inserted_2 == 0  # second write hits OR IGNORE


def test_corporate_action_pin(conn: sqlite3.Connection) -> None:
    write_corporate_actions(
        conn,
        [
            CorporateActionRecord(
                instrument=AAPL,
                action_kind="split",
                effective_ts_utc=datetime(2024, 6, 10, tzinfo=timezone.utc),
                payload={"ratio_num": 2, "ratio_den": 1},
            )
        ],
        vendor="kis",
        as_of_ts=datetime(2024, 6, 8, tzinfo=timezone.utc),
    )
    actions = list(iter_corporate_actions(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL", vendor="kis",
        from_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
        as_of_ts_pin=datetime(2024, 12, 31, tzinfo=timezone.utc),
    ))
    assert len(actions) == 1
    assert actions[0].payload == {"ratio_num": 2, "ratio_den": 1}


def test_event_null_aware_keys(conn: sqlite3.Connection) -> None:
    # An instrument-agnostic macro event (no instrument).
    write_events(
        conn,
        [
            EventRecord(
                kind="macro_cpi",
                instrument=None,
                event_ts_utc=datetime(2024, 5, 15, 12, 30, tzinfo=timezone.utc),
                payload={"value": "3.4"},
            )
        ],
        vendor="bls",
        as_of_ts=datetime(2024, 5, 15, 13, 0, tzinfo=timezone.utc),
    )
    events = list(iter_events(
        conn,
        kind="macro_cpi", vendor="bls",
        asset_class=None, venue=None, symbol=None,
        from_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
        as_of_ts_pin=datetime(2024, 6, 1, tzinfo=timezone.utc),
    ))
    assert len(events) == 1
    assert events[0].payload == {"value": "3.4"}


def test_latest_as_of_returns_max_revision(conn: sqlite3.Connection) -> None:
    write_bars(conn, [_bar(2, Decimal("180"))], vendor="kis",
               as_of_ts=datetime(2024, 1, 2, tzinfo=timezone.utc))
    write_bars(conn, [_bar(2, Decimal("181.5"))], vendor="kis",
               as_of_ts=datetime(2024, 6, 1, tzinfo=timezone.utc))
    pin = latest_as_of(
        conn,
        asset_class="equity", venue="nasdaq", symbol="AAPL",
        kind="ohlcv_1d", vendor="kis",
        bar_open_ts_utc="2024-01-02T00:00:00.000Z",
    )
    assert pin == "2024-06-01T00:00:00.000Z"
