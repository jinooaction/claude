"""스펙 028 — 체결 지연(의사결정→체결) 측정.

검증:
  - 결정→체결 초 계산(SC-028-03: 4초).
  - 페이퍼/미기록 라이브 체결은 측정 불가로 분리(SC-028-04).
  - 체결이 결정보다 이른 비정상 row 는 경고 + 측정 불가.
  - 평균·중앙·p95·최대 집계.
  - read_fills(live) 가 ORDER_INTENT.ts_utc 를 decision_at_utc 로 채운다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.performance.engine import (
    FillRecord,
    compute_fill_latency,
    read_fills,
)
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    FillPayload,
    OrderIntentPayload,
    OrderPaperFilledPayload,
)

SINCE = datetime(2026, 5, 1, tzinfo=UTC)
UNTIL = datetime(2026, 6, 1, tzinfo=UTC)


def _fill(*, decision: str | None, executed: str, symbol: str = "VOO") -> FillRecord:
    return FillRecord(
        symbol, "BUY", 1, Decimal("100"), executed, "r_dca",
        decision_at_utc=decision,
    )


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def test_latency_four_seconds() -> None:
    stats = compute_fill_latency(
        [_fill(decision="2026-05-04T13:00:00.000Z", executed="2026-05-04T13:00:04.000Z")]
    )
    assert stats.measurable_fills == 1
    assert stats.avg_sec == Decimal("4")  # 4.000 == 4
    assert stats.median_sec == Decimal("4")
    assert stats.max_sec == Decimal("4")
    assert stats.unmeasurable_fills == 0


def test_latency_subsecond() -> None:
    stats = compute_fill_latency(
        [_fill(decision="2026-05-04T13:00:00.000Z", executed="2026-05-04T13:00:00.250Z")]
    )
    assert stats.avg_sec == Decimal("0.250")


def test_paper_fill_unmeasurable() -> None:
    # 페이퍼는 decision_at_utc 가 None → 측정 비대상.
    stats = compute_fill_latency([_fill(decision=None, executed="2026-05-04T13:00:04.000Z")])
    assert stats.measurable_fills == 0
    assert stats.unmeasurable_fills == 1
    assert stats.avg_sec is None


def test_negative_latency_is_warned_and_excluded() -> None:
    stats = compute_fill_latency(
        [_fill(decision="2026-05-04T13:00:05.000Z", executed="2026-05-04T13:00:04.000Z")]
    )
    assert stats.measurable_fills == 0
    assert stats.unmeasurable_fills == 1
    assert len(stats.warnings) == 1


def test_latency_aggregates_median_p95_max() -> None:
    fills = [
        _fill(decision="2026-05-04T13:00:00.000Z", executed="2026-05-04T13:00:01.000Z"),
        _fill(decision="2026-05-04T13:00:00.000Z", executed="2026-05-04T13:00:02.000Z"),
        _fill(decision="2026-05-04T13:00:00.000Z", executed="2026-05-04T13:00:03.000Z"),
        _fill(decision="2026-05-04T13:00:00.000Z", executed="2026-05-04T13:00:10.000Z"),
    ]
    stats = compute_fill_latency(fills)
    assert stats.measurable_fills == 4
    assert stats.median_sec == Decimal("2.5")  # (2+3)/2
    assert stats.max_sec == Decimal("10")
    # p95 nearest-rank: round(0.95*3)=3 → 정렬 [1,2,3,10] 의 인덱스 3 = 10
    assert stats.p95_sec == Decimal("10")


def test_read_live_fills_populates_decision_at(conn) -> None:
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r_dca", symbol="VOO", side="BUY", order_type="MARKET",
            qty=1, decision_price_usd="100",
        ),
        rule_id="r_dca", symbol="VOO", correlation_id="o1",
        ts_utc="2026-05-04T13:00:00.000Z",
    )
    audit.append(
        conn,
        FillPayload(
            kis_fill_id="F1", qty=1, price_usd="101",
            executed_at_utc="2026-05-04T13:00:03.000Z",
        ),
        rule_id="r_dca", symbol="VOO", correlation_id="o1",
        ts_utc="2026-05-04T13:00:03.000Z",
    )
    fills = read_fills(conn, mode="live", since=SINCE, until=UNTIL)
    assert fills[0].decision_at_utc == "2026-05-04T13:00:00.000Z"
    stats = compute_fill_latency(fills)
    assert stats.measurable_fills == 1
    assert stats.avg_sec == Decimal("3")


def test_read_paper_fills_have_no_decision_at(conn) -> None:
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="r_dca", symbol="VOO", side="BUY", qty=1,
            simulated_fill_price_usd="110", quote_source="ask",
            correlation_id="c1", paper_session_id=1, reference_price_usd="100",
        ),
        rule_id="r_dca", symbol="VOO", correlation_id="c1",
        ts_utc="2026-05-04T13:00:00.000Z",
    )
    fills = read_fills(conn, mode="paper", since=SINCE, until=UNTIL)
    assert fills[0].decision_at_utc is None
    assert compute_fill_latency(fills).measurable_fills == 0
