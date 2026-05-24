"""Spec 011 P4 (US4, T015, FR-009) — 슬리피지 집계.

검증:
  - 매수/매도 부호 규약(기준가보다 비싸게 사거나 싸게 팔면 양수=불리).
  - bps·총비용 USD 손계산 일치.
  - 기준가 없는 체결은 측정 불가로 분리, 측정 가능한 것만 통계.
  - 평균·중앙(짝수/홀수) 계산.
  - read_fills 가 페이퍼 reference_price_usd / 라이브 ORDER_INTENT.limit_price_usd 를
    기준가로 채운다(추가-전용 필드, 과거 row 는 None).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.performance.engine import (
    FillRecord,
    compute_slippage,
    read_fills,
)
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    FillPayload,
    OrderIntentPayload,
    OrderPaperFilledPayload,
    OrderSubmittedPayload,
)

SINCE = datetime(2026, 5, 1, tzinfo=UTC)
UNTIL = datetime(2026, 6, 1, tzinfo=UTC)


def _fill(side, qty, price, ref, ts="2026-05-04T13:00:00.000Z"):
    return FillRecord(
        "VOO", side, qty, Decimal(price), ts, "r_dca",
        reference_price_usd=None if ref is None else Decimal(ref),
    )


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def test_buy_above_reference_is_adverse() -> None:
    stats = compute_slippage([_fill("BUY", 2, "110", "100")])
    buy = next(s for s in stats.by_side if s.side == "BUY")
    assert buy.measurable_fills == 1
    assert buy.avg_bps == Decimal("1000")  # 10/100 * 10000
    assert buy.total_cost_usd == Decimal("20")  # (110-100)*2
    assert stats.total_cost_usd == Decimal("20")
    assert stats.unmeasurable_fills == 0


def test_sell_below_reference_is_adverse() -> None:
    stats = compute_slippage([_fill("SELL", 2, "90", "100")])
    sell = next(s for s in stats.by_side if s.side == "SELL")
    assert sell.avg_bps == Decimal("1000")  # (100-90)/100 * 10000
    assert sell.total_cost_usd == Decimal("20")


def test_price_improvement_is_negative() -> None:
    stats = compute_slippage([_fill("BUY", 1, "99", "100")])
    buy = next(s for s in stats.by_side if s.side == "BUY")
    assert buy.avg_bps == Decimal("-100")  # 산 게 기준가보다 쌈 → 개선
    assert buy.total_cost_usd == Decimal("-1")


def test_unmeasurable_fills_separated() -> None:
    stats = compute_slippage(
        [_fill("BUY", 1, "110", None), _fill("BUY", 1, "120", "100")]
    )
    buy = next(s for s in stats.by_side if s.side == "BUY")
    assert buy.measurable_fills == 1
    assert stats.unmeasurable_fills == 1
    assert stats.measurable_fills == 1


def test_zero_or_negative_reference_unmeasurable() -> None:
    stats = compute_slippage([_fill("BUY", 1, "110", "0")])
    assert stats.measurable_fills == 0
    assert stats.unmeasurable_fills == 1


def test_median_even_and_odd() -> None:
    # 세 건(홀수): bps 0, 1000, 2000 → median 1000
    odd = compute_slippage(
        [
            _fill("BUY", 1, "100", "100"),
            _fill("BUY", 1, "110", "100"),
            _fill("BUY", 1, "120", "100"),
        ]
    )
    buy = next(s for s in odd.by_side if s.side == "BUY")
    assert buy.median_bps == Decimal("1000")
    # 두 건(짝수): bps 1000, 2000 → median 1500
    even = compute_slippage(
        [_fill("BUY", 1, "110", "100"), _fill("BUY", 1, "120", "100")]
    )
    buy2 = next(s for s in even.by_side if s.side == "BUY")
    assert buy2.median_bps == Decimal("1500")


def test_all_unmeasurable_graceful() -> None:
    stats = compute_slippage([_fill("BUY", 1, "110", None)])
    assert stats.measurable_fills == 0
    buy = next(s for s in stats.by_side if s.side == "BUY")
    assert buy.avg_bps is None
    assert buy.median_bps is None


# ---------------------------------------------------- read_fills 기준가 채움


def test_read_paper_fill_captures_reference(conn) -> None:
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="r_dca",
            symbol="VOO",
            side="BUY",
            qty=2,
            simulated_fill_price_usd="110",
            quote_source="ask",
            correlation_id="c1",
            paper_session_id=1,
            reference_price_usd="100",
        ),
        rule_id="r_dca",
        symbol="VOO",
        correlation_id="c1",
        ts_utc="2026-05-04T13:00:00.000Z",
    )
    fills = read_fills(conn, mode="paper", since=SINCE, until=UNTIL)
    assert len(fills) == 1
    assert fills[0].reference_price_usd == Decimal("100")
    assert compute_slippage(fills).total_cost_usd == Decimal("20")


def test_read_paper_fill_without_reference_is_none(conn) -> None:
    # reference_price_usd 미지정(과거 row 모사) → None.
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="r_dca",
            symbol="VOO",
            side="BUY",
            qty=1,
            simulated_fill_price_usd="110",
            quote_source="ask",
            correlation_id="c2",
            paper_session_id=1,
        ),
        rule_id="r_dca",
        symbol="VOO",
        correlation_id="c2",
        ts_utc="2026-05-04T13:00:00.000Z",
    )
    fills = read_fills(conn, mode="paper", since=SINCE, until=UNTIL)
    assert fills[0].reference_price_usd is None
    assert compute_slippage(fills).unmeasurable_fills == 1


def test_read_live_fill_uses_intent_limit_as_reference(conn) -> None:
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r_dca", symbol="VOO", side="BUY", order_type="LIMIT",
            qty=2, limit_price_usd="100.00",
        ),
        rule_id="r_dca", symbol="VOO", correlation_id="o1",
        ts_utc="2026-05-04T13:00:00.000Z",
    )
    audit.append(
        conn,
        OrderSubmittedPayload(kis_order_id="K1", submitted_at_utc="2026-05-04T13:00:01.000Z"),
        rule_id="r_dca", symbol="VOO", correlation_id="o1",
        ts_utc="2026-05-04T13:00:01.000Z",
    )
    audit.append(
        conn,
        FillPayload(
            kis_fill_id="F1", qty=2, price_usd="103",
            executed_at_utc="2026-05-04T13:00:02.000Z",
        ),
        rule_id="r_dca", symbol="VOO", correlation_id="o1",
        ts_utc="2026-05-04T13:00:02.000Z",
    )
    fills = read_fills(conn, mode="live", since=SINCE, until=UNTIL)
    assert len(fills) == 1
    assert fills[0].reference_price_usd == Decimal("100.00")
    stats = compute_slippage(fills)
    assert stats.total_cost_usd == Decimal("6")  # (103-100)*2
