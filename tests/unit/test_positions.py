"""Tests for `auto_invest.persistence.positions` (T032)."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.config.enums import Side
from auto_invest.persistence import db, positions


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _seed_order(
    conn: sqlite3.Connection,
    *,
    correlation_id: str,
    symbol: str,
    side: str,
    qty: int,
    state: str = "FILLED",
) -> None:
    conn.execute(
        """
        INSERT INTO orders (correlation_id, rule_id, symbol, side, order_type, qty, state)
        VALUES (?, 'r1', ?, ?, 'LIMIT', ?, ?)
        """,
        (correlation_id, symbol, side, qty, state),
    )


def _seed_fill(
    conn: sqlite3.Connection,
    *,
    correlation_id: str,
    fill_id: str,
    qty: int,
    price: str,
    ts: str,
) -> None:
    conn.execute(
        """
        INSERT INTO fills (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc)
        VALUES (?, ?, ?, ?, ?)
        """,
        (correlation_id, fill_id, qty, price, ts),
    )


# ----------------------------------------------------------------- empty


def test_get_position_returns_none_when_empty(conn):
    assert positions.get_position(conn, "AAPL") is None


def test_get_all_positions_empty(conn):
    assert positions.get_all_positions(conn) == []


# ----------------------------------------------------------------- update_from_fill


def test_first_buy_creates_position(conn):
    pos = positions.update_from_fill(
        conn,
        symbol="AAPL",
        side=Side.BUY,
        qty=10,
        price_usd=Decimal("180"),
        ts_utc="2026-05-02T13:31:00.000Z",
    )
    assert pos is not None
    assert pos.qty == 10
    assert pos.avg_cost_usd == Decimal("180")


def test_subsequent_buy_recomputes_avg_cost(conn):
    positions.update_from_fill(
        conn, symbol="AAPL", side=Side.BUY, qty=10,
        price_usd=Decimal("180"), ts_utc="t1",
    )
    pos = positions.update_from_fill(
        conn, symbol="AAPL", side=Side.BUY, qty=10,
        price_usd=Decimal("200"), ts_utc="t2",
    )
    assert pos is not None
    assert pos.qty == 20
    # (10*180 + 10*200) / 20 = 190
    assert pos.avg_cost_usd == Decimal("190")


def test_partial_sell_keeps_avg_cost(conn):
    positions.update_from_fill(
        conn, symbol="AAPL", side=Side.BUY, qty=10,
        price_usd=Decimal("180"), ts_utc="t1",
    )
    pos = positions.update_from_fill(
        conn, symbol="AAPL", side=Side.SELL, qty=3,
        price_usd=Decimal("200"), ts_utc="t2",
    )
    assert pos is not None
    assert pos.qty == 7
    assert pos.avg_cost_usd == Decimal("180")


def test_full_sell_deletes_row(conn):
    positions.update_from_fill(
        conn, symbol="AAPL", side=Side.BUY, qty=10,
        price_usd=Decimal("180"), ts_utc="t1",
    )
    pos = positions.update_from_fill(
        conn, symbol="AAPL", side=Side.SELL, qty=10,
        price_usd=Decimal("200"), ts_utc="t2",
    )
    assert pos is None
    assert positions.get_position(conn, "AAPL") is None


# ----------------------------------------------------------------- rebuild


def test_rebuild_from_empty_fills(conn):
    positions.rebuild_from_fills(conn)
    assert positions.get_all_positions(conn) == []


def test_rebuild_aggregates_buys_into_avg_cost(conn):
    _seed_order(conn, correlation_id="o1", symbol="AAPL", side="BUY", qty=10)
    _seed_fill(conn, correlation_id="o1", fill_id="f1", qty=10,
               price="180", ts="2026-05-02T13:31:00.000Z")
    _seed_order(conn, correlation_id="o2", symbol="AAPL", side="BUY", qty=10)
    _seed_fill(conn, correlation_id="o2", fill_id="f2", qty=10,
               price="200", ts="2026-05-02T13:32:00.000Z")

    positions.rebuild_from_fills(conn)

    pos = positions.get_position(conn, "AAPL")
    assert pos is not None
    assert pos.qty == 20
    assert pos.avg_cost_usd == Decimal("190")


def test_rebuild_handles_partial_sell(conn):
    _seed_order(conn, correlation_id="o1", symbol="AAPL", side="BUY", qty=10)
    _seed_fill(conn, correlation_id="o1", fill_id="f1", qty=10,
               price="180", ts="t1")
    _seed_order(conn, correlation_id="o2", symbol="AAPL", side="SELL", qty=3)
    _seed_fill(conn, correlation_id="o2", fill_id="f2", qty=3,
               price="220", ts="t2")

    positions.rebuild_from_fills(conn)

    pos = positions.get_position(conn, "AAPL")
    assert pos is not None
    assert pos.qty == 7
    assert pos.avg_cost_usd == Decimal("180")


def test_rebuild_drops_fully_closed_positions(conn):
    _seed_order(conn, correlation_id="o1", symbol="AAPL", side="BUY", qty=10)
    _seed_fill(conn, correlation_id="o1", fill_id="f1", qty=10,
               price="180", ts="t1")
    _seed_order(conn, correlation_id="o2", symbol="AAPL", side="SELL", qty=10)
    _seed_fill(conn, correlation_id="o2", fill_id="f2", qty=10,
               price="200", ts="t2")

    positions.rebuild_from_fills(conn)

    assert positions.get_position(conn, "AAPL") is None


def test_rebuild_handles_multiple_symbols(conn):
    for symbol, qty, price in [("AAPL", 10, "180"), ("MSFT", 5, "400")]:
        cid = f"o-{symbol}"
        _seed_order(conn, correlation_id=cid, symbol=symbol, side="BUY", qty=qty)
        _seed_fill(conn, correlation_id=cid, fill_id=f"f-{symbol}",
                   qty=qty, price=price, ts="t1")

    positions.rebuild_from_fills(conn)

    aapl = positions.get_position(conn, "AAPL")
    msft = positions.get_position(conn, "MSFT")
    assert aapl is not None and aapl.qty == 10
    assert msft is not None and msft.qty == 5


def test_rebuild_is_idempotent(conn):
    _seed_order(conn, correlation_id="o1", symbol="AAPL", side="BUY", qty=10)
    _seed_fill(conn, correlation_id="o1", fill_id="f1", qty=10,
               price="180", ts="t1")

    positions.rebuild_from_fills(conn)
    snapshot1 = positions.get_all_positions(conn)
    positions.rebuild_from_fills(conn)
    snapshot2 = positions.get_all_positions(conn)

    assert snapshot1 == snapshot2
