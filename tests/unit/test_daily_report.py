"""Tests for `auto_invest.reports.daily` (T053)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.config.enums import Side
from auto_invest.persistence import audit, db
from auto_invest.persistence import positions as positions_mod
from auto_invest.persistence.audit import (
    FillPayload,
    HaltSetPayload,
    OrderIntentPayload,
    OrderPaperFilledPayload,
    OrderRejectedByGatePayload,
    OrderSubmittedPayload,
    ReconciliationOkPayload,
)
from auto_invest.reports.daily import (
    build_report,
    render_json,
    render_markdown,
    write_report,
)


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _seed_session(conn) -> None:
    """Seed a session with one fill, one rejection, and one OK reconcile."""
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r1",
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            qty=5,
            limit_price_usd="100.00",
        ),
        rule_id="r1",
        symbol="AAPL",
        correlation_id="ord-1",
        ts_utc="2026-05-04T13:31:00.000Z",
    )
    audit.append(
        conn,
        OrderSubmittedPayload(
            kis_order_id="K-1",
            submitted_at_utc="2026-05-04T13:31:01.000Z",
        ),
        rule_id="r1",
        symbol="AAPL",
        correlation_id="ord-1",
        ts_utc="2026-05-04T13:31:01.000Z",
    )
    audit.append(
        conn,
        FillPayload(
            kis_fill_id="F-1",
            qty=5,
            price_usd="100",
            executed_at_utc="2026-05-04T13:31:02.000Z",
        ),
        rule_id="r1",
        symbol="AAPL",
        correlation_id="ord-1",
        ts_utc="2026-05-04T13:31:02.000Z",
    )
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r2",
            symbol="MSFT",
            side="BUY",
            order_type="LIMIT",
            qty=100,
            limit_price_usd="500.00",
        ),
        rule_id="r2",
        symbol="MSFT",
        correlation_id="ord-2",
        ts_utc="2026-05-04T14:00:00.000Z",
    )
    audit.append(
        conn,
        OrderRejectedByGatePayload(
            gate="per_trade_cap_gate",
            reason="notional 50000 exceeds per-trade cap 500",
            metadata={"cap_pct": "5"},
        ),
        rule_id="r2",
        symbol="MSFT",
        correlation_id="ord-2",
        ts_utc="2026-05-04T14:00:00.500Z",
    )
    audit.append(
        conn,
        ReconciliationOkPayload(
            started_at_utc="2026-05-04T20:00:00.000Z",
            finished_at_utc="2026-05-04T20:00:01.000Z",
        ),
        ts_utc="2026-05-04T20:00:01.000Z",
    )
    conn.execute(
        """
        INSERT INTO reconciliation_runs
            (started_at_utc, finished_at_utc, result, mismatch_payload_json)
        VALUES ('2026-05-04T20:00:00.000Z', '2026-05-04T20:00:01.000Z', 'OK', NULL)
        """
    )
    positions_mod.update_from_fill(
        conn,
        symbol="AAPL",
        side=Side.BUY,
        qty=5,
        price_usd=Decimal("100"),
        ts_utc="2026-05-04T13:31:02.000Z",
    )


# ----------------------------------------------------------- empty


def test_empty_session_produces_zeroed_report(conn):
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    assert report.counters == {}
    assert report.rules == []
    assert report.rejections == []
    assert report.positions == []
    assert report.reconciliation == "NONE"
    assert report.halt is None


# ----------------------------------------------------------- populated


def test_report_counts_orders_and_fills(conn):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    assert report.counters["orders_attempted"] == 2
    assert report.counters["orders_submitted"] == 1
    assert report.counters["orders_rejected_by_gate"] == 1
    assert report.counters["fills"] == 1


def test_report_per_rule_activity(conn):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    rule_ids = [r.rule_id for r in report.rules]
    assert rule_ids == ["r1", "r2"]
    r1, r2 = report.rules
    assert r1.triggers == 1 and r1.submitted == 1 and r1.rejected == 0
    assert r2.triggers == 1 and r2.submitted == 0 and r2.rejected == 1


def test_report_lists_rejections_with_gate_and_metadata(conn):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    assert len(report.rejections) == 1
    rej = report.rejections[0]
    assert rej.gate == "per_trade_cap_gate"
    assert "exceeds" in rej.reason
    assert rej.metadata["cap_pct"] == "5"


def test_report_includes_positions(conn):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    assert report.positions == [{"symbol": "AAPL", "qty": 5, "avg_cost_usd": "100"}]


def test_report_reflects_reconciliation_result(conn):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    assert report.reconciliation == "OK"


def test_report_reflects_active_halt(conn):
    audit.append(
        conn,
        HaltSetPayload(reason="manual"),
        ts_utc="2026-05-04T15:00:00.000Z",
    )
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    assert report.halt is not None
    assert report.halt["reason"] == "manual"


# ----------------------------------------------------------- date isolation


def test_report_filters_by_session_date(conn):
    audit.append(
        conn,
        HaltSetPayload(reason="day-1"),
        ts_utc="2026-05-03T15:00:00.000Z",
    )
    audit.append(
        conn,
        HaltSetPayload(reason="day-2"),
        ts_utc="2026-05-04T15:00:00.000Z",
    )
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    assert report.halt["reason"] == "day-2"


# ----------------------------------------------------------- rendering


def test_render_markdown_contains_all_sections(conn):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    md = render_markdown(report)
    for section in (
        "## Summary",
        "## Per-rule activity",
        "## Risk-gate rejections",
        "## Positions (current)",
    ):
        assert section in md
    assert "AAPL" in md
    assert "per_trade_cap_gate" in md


def test_render_json_round_trips(conn):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    payload = json.loads(render_json(report))
    assert payload["counters"]["orders_attempted"] == 2
    assert payload["reconciliation"] == "OK"
    assert payload["positions"][0]["symbol"] == "AAPL"


def test_byte_stable_when_inputs_unchanged(conn):
    _seed_session(conn)
    fixed = "2026-05-05T04:00:00Z"
    md_a = render_markdown(build_report(conn, session_date="2026-05-04", generated_at=fixed))
    json_a = render_json(build_report(conn, session_date="2026-05-04", generated_at=fixed))
    md_b = render_markdown(build_report(conn, session_date="2026-05-04", generated_at=fixed))
    json_b = render_json(build_report(conn, session_date="2026-05-04", generated_at=fixed))
    assert md_a == md_b
    assert json_a == json_b


# ----------------------------------------------------------- performance (T013)


def _paper_fill(conn, *, symbol, side, qty, price, ts, rule_id="r_dca"):
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id=rule_id,
            symbol=symbol,
            side=side,
            qty=qty,
            simulated_fill_price_usd=price,
            quote_source="last",
            correlation_id=f"paper-{symbol}-{ts}",
            paper_session_id=1,
        ),
        rule_id=rule_id,
        symbol=symbol,
        correlation_id=f"paper-{symbol}-{ts}",
        ts_utc=ts,
    )


def test_performance_section_absent_by_default(conn):
    """후방 호환 — include_performance 미지정 시 섹션 없음(기존 호출부 불변)."""
    _seed_session(conn)
    report = build_report(conn, session_date="2026-05-04", generated_at="x")
    assert report.performance is None
    assert "## Performance" not in render_markdown(report)
    assert json.loads(render_json(report))["performance"] is None


def test_performance_section_realized_and_rolling(conn):
    """그날 매수→매도 1라운드 청산 → 당일 실현 손익 + 롤링 위험조정 요약."""
    _paper_fill(conn, symbol="VOO", side="BUY", qty=2, price="100", ts="2026-05-04T13:00:00.000Z")
    _paper_fill(conn, symbol="VOO", side="SELL", qty=2, price="110", ts="2026-05-04T15:00:00.000Z")
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
        include_performance=True,
    )
    perf = report.performance
    assert perf is not None
    assert perf.mode == "paper"
    assert perf.day_fills == 2
    assert perf.day_realized_pnl_usd == Decimal("20")  # (110-100)*2
    assert perf.rolling_closed_trades == 1
    assert perf.rolling_win_rate == Decimal("1")  # 1/1 이익 청산

    md = render_markdown(report)
    assert "## Performance (성과)" in md
    assert "paper" in md

    payload = json.loads(render_json(report))["performance"]
    assert payload["mode"] == "paper"
    assert payload["day_realized_pnl_usd"] == "20"
    assert payload["rolling_closed_trades"] == 1


def test_performance_section_no_fills_is_graceful(conn):
    """체결 0건 — 섹션은 존재하되 실현 0·롤링 N/A, 예외 없음."""
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="x",
        include_performance=True,
    )
    perf = report.performance
    assert perf is not None
    assert perf.day_fills == 0
    assert perf.day_realized_pnl_usd == Decimal("0")
    assert perf.rolling_closed_trades == 0
    assert perf.rolling_sharpe is None
    md = render_markdown(report)
    assert "## Performance (성과)" in md
    assert "N/A" in md


def test_performance_section_byte_stable(conn):
    """결정론 — 같은 audit_log 에 대해 성과 섹션 포함 출력이 바이트 동일."""
    _paper_fill(conn, symbol="VOO", side="BUY", qty=1, price="100", ts="2026-05-04T13:00:00.000Z")
    _paper_fill(conn, symbol="VOO", side="SELL", qty=1, price="90", ts="2026-05-04T15:00:00.000Z")
    fixed = "2026-05-05T04:00:00Z"
    a = render_json(
        build_report(conn, session_date="2026-05-04", generated_at=fixed, include_performance=True)
    )
    b = render_json(
        build_report(conn, session_date="2026-05-04", generated_at=fixed, include_performance=True)
    )
    assert a == b


def test_write_report_creates_files(conn, tmp_path: Path):
    _seed_session(conn)
    report = build_report(
        conn,
        session_date="2026-05-04",
        generated_at="2026-05-05T04:00:00Z",
    )
    md_path, json_path = write_report(report, output_root=tmp_path)
    assert md_path.exists() and json_path.exists()
    assert md_path.parent.name == "2026-05-04"
