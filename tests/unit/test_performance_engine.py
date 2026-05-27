"""Spec 011 — 라이브 성과 측정 엔진 단위 테스트.

검증:
  - 실현 손익(평균단가 기준), 미실현 손익(주입 시세), 투입 대비 수익률.
  - 룰별·종목별 분해 손익 합 = 전체 손익 (SC-003 합산 보존).
  - 빈 입력 → N/A, 예외 없음 (FR-010).
  - 페이퍼/라이브 모드 audit_log 읽기 (라이브는 ORDER_INTENT side 조인).
  - 시세 누락 → 미실현 "조회 불가", 실현은 정상 (FR-005).
  - 공매도/데이터 품질 경고.
  - JSON 출력 스키마 버전 (FR-011).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from auto_invest.performance.engine import (
    FillRecord,
    build_performance_report,
    compute_performance,
    read_fills,
    reconstruct,
    render_text,
)
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    FillPayload,
    OrderIntentPayload,
    OrderPaperFilledPayload,
    OrderSubmittedPayload,
    PaperRunStartedPayload,
)

SINCE = datetime(2000, 1, 1, tzinfo=UTC)
UNTIL = datetime(2099, 1, 1, tzinfo=UTC)


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _fill(symbol, side, qty, price, rule_id="R", ts="2026-05-20T00:00:00.000Z"):
    return FillRecord(symbol, side, qty, Decimal(price), ts, rule_id)


# --------------------------------------------------------------- reconstruct


def test_realized_pnl_on_closed_round() -> None:
    """매수 100 → 매도 110, 수량 1 → 실현 +10, 포지션 청산, 미실현 0."""
    fills = [_fill("AAPL", "BUY", 1, "100"), _fill("AAPL", "SELL", 1, "110")]
    rep = compute_performance(fills, {}, mode="paper", since=SINCE, until=UNTIL)
    assert rep.realized_pnl_usd == Decimal("10")
    assert rep.unrealized_pnl_usd == Decimal("0")
    assert rep.total_pnl_usd == Decimal("10")
    # 투입 = 100, 수익률 = 10/100*100 = 10%
    assert rep.return_pct == Decimal("10")


def test_unrealized_pnl_open_position() -> None:
    """매수만 있고 시세가 매수가보다 높으면 미실현 양수."""
    fills = [_fill("AAPL", "BUY", 2, "100")]
    rep = compute_performance(
        fills, {"AAPL": Decimal("120")}, mode="paper", since=SINCE, until=UNTIL
    )
    assert rep.realized_pnl_usd == Decimal("0")
    assert rep.unrealized_pnl_usd == Decimal("40")  # (120-100)*2
    assert rep.total_pnl_usd == Decimal("40")
    sym = rep.per_symbol[0]
    assert sym.mark_price_usd == Decimal("120")
    assert sym.market_value_usd == Decimal("240")


def test_average_cost_basis() -> None:
    """매수 100×1 + 매수 200×1 → avg 150. 매도 180×1 → 실현 (180-150)=30."""
    fills = [
        _fill("X", "BUY", 1, "100"),
        _fill("X", "BUY", 1, "200"),
        _fill("X", "SELL", 1, "180"),
    ]
    positions, _, gross, _ = reconstruct(fills)
    pos = positions["X"]
    assert pos.avg_cost_usd == Decimal("150")
    assert pos.qty == 1
    assert pos.realized_pnl_usd == Decimal("30")
    assert gross == Decimal("300")


def test_breakdown_sum_preservation() -> None:
    """룰별·종목별 분해 손익 합 = 전체 손익 (SC-003)."""
    fills = [
        _fill("AAPL", "BUY", 1, "100", rule_id="ra"),
        _fill("AAPL", "SELL", 1, "130", rule_id="ra"),
        _fill("MSFT", "BUY", 2, "50", rule_id="rb"),
    ]
    marks = {"MSFT": Decimal("60")}
    rep = compute_performance(fills, marks, mode="paper", since=SINCE, until=UNTIL)
    by_sym_total = sum((s.total_pnl_usd for s in rep.per_symbol), Decimal("0"))
    assert by_sym_total == rep.total_pnl_usd
    # 룰별 realized 합 = 전체 realized
    by_rule_realized = sum((r.realized_pnl_usd for r in rep.per_rule), Decimal("0"))
    assert by_rule_realized == rep.realized_pnl_usd
    # ra: realized 30, rb: realized 0 + 미실현 (60-50)*2=20
    assert rep.realized_pnl_usd == Decimal("30")
    assert rep.unrealized_pnl_usd == Decimal("20")
    assert rep.total_pnl_usd == Decimal("50")


def test_empty_fills_no_crash() -> None:
    """체결 0건 → 모든 값 0/N-A, 예외 없음 (FR-010)."""
    rep = compute_performance([], {}, mode="paper", since=SINCE, until=UNTIL)
    assert rep.fills_count == 0
    assert rep.realized_pnl_usd == Decimal("0")
    assert rep.total_pnl_usd == Decimal("0")
    assert rep.return_pct is None
    assert rep.per_symbol == []
    assert "performance" in render_text(rep)


def test_missing_mark_degrades_gracefully() -> None:
    """시세 없으면 미실현 '조회 불가', 실현은 정상 (FR-005)."""
    fills = [
        _fill("AAPL", "BUY", 1, "100"),
        _fill("AAPL", "SELL", 1, "120"),  # 실현 20, 청산
        _fill("MSFT", "BUY", 1, "50"),  # 미청산, 시세 없음
    ]
    rep = compute_performance(fills, {}, mode="paper", since=SINCE, until=UNTIL)
    assert rep.realized_pnl_usd == Decimal("20")
    assert "MSFT" in rep.unmarked_symbols
    msft = next(s for s in rep.per_symbol if s.symbol == "MSFT")
    assert msft.unrealized_pnl_usd is None
    assert msft.mark_price_usd is None


def test_oversell_warning() -> None:
    """보유보다 많이 팔면 경고 + 보유분까지만 실현."""
    fills = [_fill("X", "BUY", 1, "100"), _fill("X", "SELL", 3, "120")]
    positions, _, _, warnings = reconstruct(fills)
    assert positions["X"].qty == 0
    assert positions["X"].realized_pnl_usd == Decimal("20")  # 1주분만
    assert any("매도 수량" in w for w in warnings)


def test_loss_is_negative() -> None:
    """매수 100 → 매도 80 → 실현 -20."""
    fills = [_fill("X", "BUY", 1, "100"), _fill("X", "SELL", 1, "80")]
    rep = compute_performance(fills, {}, mode="paper", since=SINCE, until=UNTIL)
    assert rep.realized_pnl_usd == Decimal("-20")
    assert rep.return_pct == Decimal("-20")


def test_to_json_dict_schema_version() -> None:
    rep = compute_performance(
        [_fill("X", "BUY", 1, "10")], {}, mode="live", since=SINCE, until=UNTIL
    )
    d = rep.to_json_dict()
    assert d["schema_version"] == "1.2"
    assert d["mode"] == "live"
    assert "per_symbol" in d and "per_rule" in d
    assert "risk" in d


# --------------------------------------------------------------- read_fills


def test_read_paper_fills(conn) -> None:
    """ORDER_PAPER_FILLED 를 읽어 정규화."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-20T00:00:00.000Z", host="t",
        ),
    )
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="R", symbol="AAPL", side="BUY", qty=2,
            simulated_fill_price_usd="100.00", quote_source="ask",
            correlation_id="c1", paper_session_id=sid,
        ),
        rule_id="R", symbol="AAPL", correlation_id="c1",
    )
    fills = read_fills(conn, mode="paper", since=SINCE, until=UNTIL)
    assert len(fills) == 1
    assert fills[0].symbol == "AAPL"
    assert fills[0].side == "BUY"
    assert fills[0].qty == 2
    assert fills[0].price_usd == Decimal("100.00")


def test_read_live_fills_joins_side_from_intent(conn) -> None:
    """라이브 FILL 은 같은 correlation_id 의 ORDER_INTENT 에서 side 를 가져온다."""
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="R", symbol="AAPL", side="SELL", order_type="MARKET", qty=1,
        ),
        rule_id="R", symbol="AAPL", correlation_id="ord-1",
    )
    audit.append(
        conn,
        OrderSubmittedPayload(kis_order_id="k1", submitted_at_utc="2026-05-20T00:00:00.000Z"),
        rule_id="R", symbol="AAPL", correlation_id="ord-1",
    )
    audit.append(
        conn,
        FillPayload(
            kis_fill_id="f1", qty=1, price_usd="130.00",
            executed_at_utc="2026-05-20T00:01:00.000Z",
        ),
        rule_id="R", symbol="AAPL", correlation_id="ord-1",
    )
    fills = read_fills(conn, mode="live", since=SINCE, until=UNTIL)
    assert len(fills) == 1
    assert fills[0].side == "SELL"
    assert fills[0].symbol == "AAPL"
    assert fills[0].price_usd == Decimal("130.00")


def test_paper_and_live_do_not_mix(conn) -> None:
    """같은 DB 에 페이퍼·라이브 체결이 섞여도 모드별로 분리 집계 (FR-003)."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-20T00:00:00.000Z", host="t",
        ),
    )
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="R", symbol="AAPL", side="BUY", qty=1,
            simulated_fill_price_usd="100.00", quote_source="ask",
            correlation_id="c1", paper_session_id=sid,
        ),
        rule_id="R", symbol="AAPL", correlation_id="c1",
    )
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="R", symbol="MSFT", side="BUY", order_type="MARKET", qty=1,
        ),
        rule_id="R", symbol="MSFT", correlation_id="ord-1",
    )
    audit.append(
        conn,
        FillPayload(
            kis_fill_id="f1", qty=1, price_usd="200.00",
            executed_at_utc="2026-05-20T00:01:00.000Z",
        ),
        rule_id="R", symbol="MSFT", correlation_id="ord-1",
    )
    paper = read_fills(conn, mode="paper", since=SINCE, until=UNTIL)
    live = read_fills(conn, mode="live", since=SINCE, until=UNTIL)
    assert {f.symbol for f in paper} == {"AAPL"}
    assert {f.symbol for f in live} == {"MSFT"}


def test_build_performance_report_read_only(conn) -> None:
    """build_performance_report 는 audit_log row 를 변경하지 않는다 (SC-005)."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-20T00:00:00.000Z", host="t",
        ),
    )
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="R", symbol="AAPL", side="BUY", qty=1,
            simulated_fill_price_usd="100.00", quote_source="ask",
            correlation_id="c1", paper_session_id=sid,
        ),
        rule_id="R", symbol="AAPL", correlation_id="c1",
    )
    before = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    rep = build_performance_report(
        conn, mode="paper", since=SINCE, until=UNTIL, marks={"AAPL": Decimal("110")}
    )
    after = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    assert before == after  # 새 row 안 생김
    assert rep.unrealized_pnl_usd == Decimal("10")
