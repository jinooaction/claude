"""Spec 009 T017 — 가상 포지션 derived view 단위 테스트.

`recompute_virtual_positions`가 ORDER_PAPER_FILLED 이벤트 시퀀스에서:
  - BUY 평균단가를 가중평균으로 정확히 계산.
  - SELL 실현 손익을 (sell - avg_cost) × qty로 누적.
  - paper_session_id로 필터.
  - since/until 범위 필터.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from auto_invest.paper.virtual_positions import (
    recompute_virtual_positions,
)
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import OrderPaperFilledPayload


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _fill(
    conn,
    *,
    rule_id: str = "r",
    symbol: str = "AAPL",
    side: str = "BUY",
    qty: int = 1,
    price: str = "100.00",
    paper_session_id: int = 1,
    correlation_id: str = "ord-1",
) -> None:
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id=rule_id,
            symbol=symbol,
            side=side,
            qty=qty,
            simulated_fill_price_usd=price,
            quote_source="ask" if side == "BUY" else "bid",
            correlation_id=correlation_id,
            paper_session_id=paper_session_id,
        ),
        rule_id=rule_id,
        symbol=symbol,
        correlation_id=correlation_id,
    )


def test_empty_audit_returns_empty_dict(conn) -> None:
    assert recompute_virtual_positions(conn) == {}


def test_single_buy(conn) -> None:
    _fill(conn, side="BUY", qty=5, price="100.00")
    positions = recompute_virtual_positions(conn)
    assert "AAPL" in positions
    pos = positions["AAPL"]
    assert pos.qty == 5
    assert pos.avg_cost_usd == Decimal("100.00")
    assert pos.realized_pnl_usd == Decimal("0")
    assert pos.last_fill_price_usd == Decimal("100.00")


def test_two_buys_weighted_average(conn) -> None:
    """첫 BUY 5 @ 100, 두 번째 BUY 5 @ 110 → 평균 105."""
    _fill(conn, side="BUY", qty=5, price="100.00", correlation_id="ord-1")
    _fill(conn, side="BUY", qty=5, price="110.00", correlation_id="ord-2")
    positions = recompute_virtual_positions(conn)
    pos = positions["AAPL"]
    assert pos.qty == 10
    assert pos.avg_cost_usd == Decimal("105.00")


def test_buy_then_sell_realizes_pnl(conn) -> None:
    """BUY 10 @ 100, SELL 4 @ 120 → realized = (120-100)*4 = +80."""
    _fill(conn, side="BUY", qty=10, price="100.00", correlation_id="ord-1")
    _fill(conn, side="SELL", qty=4, price="120.00", correlation_id="ord-2")
    positions = recompute_virtual_positions(conn)
    pos = positions["AAPL"]
    assert pos.qty == 6
    assert pos.avg_cost_usd == Decimal("100.00")
    assert pos.realized_pnl_usd == Decimal("80")


def test_buy_sell_at_loss(conn) -> None:
    """BUY 5 @ 200, SELL 5 @ 180 → realized = (180-200)*5 = -100."""
    _fill(conn, side="BUY", qty=5, price="200.00", correlation_id="ord-1")
    _fill(conn, side="SELL", qty=5, price="180.00", correlation_id="ord-2")
    positions = recompute_virtual_positions(conn)
    pos = positions["AAPL"]
    assert pos.qty == 0
    assert pos.realized_pnl_usd == Decimal("-100")


def test_multiple_symbols_independent(conn) -> None:
    _fill(conn, symbol="AAPL", side="BUY", qty=5, price="100.00", correlation_id="ord-1")
    _fill(conn, symbol="MSFT", side="BUY", qty=10, price="200.00", correlation_id="ord-2")
    positions = recompute_virtual_positions(conn)
    assert set(positions.keys()) == {"AAPL", "MSFT"}
    assert positions["AAPL"].qty == 5
    assert positions["MSFT"].qty == 10


def test_paper_session_filter(conn) -> None:
    """다른 paper_session_id의 fill은 필터에 의해 제외된다."""
    _fill(conn, paper_session_id=1, qty=5, price="100.00", correlation_id="ord-1")
    _fill(conn, paper_session_id=2, qty=10, price="200.00", correlation_id="ord-2")

    s1 = recompute_virtual_positions(conn, paper_session_id=1)
    assert s1["AAPL"].qty == 5

    s2 = recompute_virtual_positions(conn, paper_session_id=2)
    assert s2["AAPL"].qty == 10

    all_sessions = recompute_virtual_positions(conn)
    # 두 세션 합산 = 15 (avg 가중평균 = (5*100 + 10*200)/15 = 2500/15 ≈ 166.67)
    assert all_sessions["AAPL"].qty == 15


def test_time_range_filter(conn) -> None:
    """since/until 범위 필터."""
    # 이 테스트는 audit.append가 wall clock을 쓰므로 since=now()로 한 번에 다 잡힘.
    # 시간 필터링 동작을 보려면 ts_utc를 명시적으로 INSERT.
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="r",
            symbol="AAPL",
            side="BUY",
            qty=5,
            simulated_fill_price_usd="100.00",
            quote_source="ask",
            correlation_id="ord-old",
            paper_session_id=1,
        ),
        ts_utc="2026-01-01T00:00:00.000Z",
        rule_id="r",
        symbol="AAPL",
        correlation_id="ord-old",
    )
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="r",
            symbol="AAPL",
            side="BUY",
            qty=10,
            simulated_fill_price_usd="200.00",
            quote_source="ask",
            correlation_id="ord-new",
            paper_session_id=1,
        ),
        ts_utc="2026-05-01T00:00:00.000Z",
        rule_id="r",
        symbol="AAPL",
        correlation_id="ord-new",
    )

    # since 2026-03-01 → new만 포함
    cutoff = datetime(2026, 3, 1, tzinfo=UTC)
    only_new = recompute_virtual_positions(conn, since=cutoff)
    assert only_new["AAPL"].qty == 10

    # until 2026-03-01 → old만 포함
    only_old = recompute_virtual_positions(conn, until=cutoff)
    assert only_old["AAPL"].qty == 5


def test_excludes_non_paper_events(conn) -> None:
    """live의 FillPayload는 가상 포지션에 포함되지 않아야 한다 (FR-011)."""
    from decimal import Decimal as _D

    from auto_invest.persistence.audit import FillPayload

    audit.append(
        conn,
        FillPayload(
            kis_fill_id="kis-1",
            qty=100,
            price_usd="999.00",
            executed_at_utc="2026-05-19T12:00:00.000Z",
        ),
        symbol="AAPL",
    )
    # paper fill 1건만 추가
    _fill(conn, side="BUY", qty=5, price="100.00")
    positions = recompute_virtual_positions(conn)
    assert positions["AAPL"].qty == 5  # live 100건은 무시
    assert positions["AAPL"].avg_cost_usd == _D("100.00")
