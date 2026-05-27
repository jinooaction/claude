"""Spec 011 P3 T014 (FR-014) — LIVE_PERFORMANCE_SNAPSHOT 추가-전용 이벤트.

검증:
  - snapshot_fields 가 PerformanceReport 를 평탄화해 payload 필드를 만든다.
  - 청산 0건이면 위험조정 필드는 None.
  - LivePerformanceSnapshotPayload 가 audit.append 로 기록되고 읽혀온다(append-only).
  - 기록은 기존 row 를 건드리지 않는 순수 추가다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.performance.engine import (
    FillRecord,
    compute_performance,
    snapshot_fields,
)
from auto_invest.persistence import audit, db

SINCE = datetime(2026, 5, 1, tzinfo=UTC)
UNTIL = datetime(2026, 6, 1, tzinfo=UTC)


def _fill(symbol, side, qty, price, ts):
    return FillRecord(symbol, side, qty, Decimal(price), ts, "r_dca")


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _report(fills):
    return compute_performance(fills, {}, mode="paper", since=SINCE, until=UNTIL)


def test_snapshot_fields_flatten_closed_trades() -> None:
    fills = [
        _fill("VOO", "BUY", 2, "100", "2026-05-04T13:00:00.000Z"),
        _fill("VOO", "SELL", 2, "110", "2026-05-04T15:00:00.000Z"),
    ]
    fields = snapshot_fields(_report(fills), computed_at_utc="2026-05-05T00:00:00.000Z")
    assert fields["mode"] == "paper"
    assert fields["schema_version"] == "1.2"
    assert fields["fills_count"] == 2
    assert fields["realized_pnl_usd"] == "20"
    assert fields["total_pnl_usd"] == "20"
    assert fields["closed_trades"] == 1
    assert fields["win_rate"] == "1"
    assert fields["computed_at_utc"] == "2026-05-05T00:00:00.000Z"


def test_snapshot_fields_no_trades_null_risk() -> None:
    fields = snapshot_fields(_report([]), computed_at_utc="2026-05-05T00:00:00.000Z")
    assert fields["fills_count"] == 0
    assert fields["closed_trades"] == 0
    assert fields["win_rate"] is None
    assert fields["sharpe_ratio"] is None
    assert fields["return_pct"] is None


def test_snapshot_appends_and_reads_back(conn) -> None:
    fills = [
        _fill("VOO", "BUY", 1, "100", "2026-05-04T13:00:00.000Z"),
        _fill("VOO", "SELL", 1, "115", "2026-05-04T15:00:00.000Z"),
    ]
    fields = snapshot_fields(_report(fills), computed_at_utc="2026-05-05T00:00:00.000Z")
    seq = audit.append(conn, audit.LivePerformanceSnapshotPayload(**fields))
    assert seq >= 1

    rows = [r for r in audit.read_all(conn) if r["event_type"] == "LIVE_PERFORMANCE_SNAPSHOT"]
    assert len(rows) == 1
    payload = audit.parse_payload(rows[0])
    assert payload["event_type"] == "LIVE_PERFORMANCE_SNAPSHOT"
    assert payload["realized_pnl_usd"] == "15"
    assert payload["closed_trades"] == 1


def test_snapshot_is_pure_addition(conn) -> None:
    """스냅샷 기록 전후로 기존 row 수만 +1, 기존 row 는 불변(append-only)."""
    audit.append(conn, audit.HaltSetPayload(reason="seed"))
    before = audit.read_all(conn)
    fields = snapshot_fields(_report([]), computed_at_utc="2026-05-05T00:00:00.000Z")
    audit.append(conn, audit.LivePerformanceSnapshotPayload(**fields))
    after = audit.read_all(conn)
    assert len(after) == len(before) + 1
    # 기존 row 의 payload 가 그대로다.
    assert after[0]["payload_json"] == before[0]["payload_json"]
