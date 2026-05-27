"""Spec 014 — 손실 서킷 브레이커 단위 테스트 (T002·T005·T007)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from auto_invest.config.caps import SizingCaps
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    CircuitBreakerTrippedPayload,
    OrderPaperFilledPayload,
    PaperRunStartedPayload,
)
from auto_invest.risk.circuit_breaker import (
    BreakerLimits,
    evaluate,
    evaluate_from_audit,
)

NOW = datetime(2026, 5, 26, 15, 0, tzinfo=UTC)


def _caps(
    *,
    enabled: bool = True,
    daily: str = "10",
    drawdown: str = "20",
) -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
        circuit_breaker_enabled=enabled,
        daily_loss_limit_pct=Decimal(daily),
        max_total_drawdown_pct=Decimal(drawdown),
    )


# --------------------------------------------------------- T002: caps fields


def test_caps_breaker_defaults_enabled() -> None:
    """기존 6필드만 준 설정도 그대로 검증되고, 브레이커는 기본 활성·기본 한도."""
    c = SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )
    assert c.circuit_breaker_enabled is True
    assert c.daily_loss_limit_pct == Decimal("10")
    assert c.max_total_drawdown_pct == Decimal("20")


def test_caps_breaker_override() -> None:
    c = _caps(enabled=False, daily="3", drawdown="7")
    assert c.circuit_breaker_enabled is False
    assert c.daily_loss_limit_pct == Decimal("3")
    assert c.max_total_drawdown_pct == Decimal("7")


@pytest.mark.parametrize("bad", ["0", "-1", "150"])
def test_caps_breaker_range_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        _caps(daily=bad)
    with pytest.raises(ValidationError):
        _caps(drawdown=bad)


# --------------------------------------------------------- T005: pure evaluate


def test_daily_loss_trips() -> None:
    d = evaluate(
        starting_capital=Decimal("100"),
        realized_pnl_today=Decimal("-12"),
        current_equity=Decimal("95"),
        limits=BreakerLimits.from_caps(_caps()),
    )
    assert d.tripped is True
    assert d.breached == ["daily_loss"]


def test_daily_loss_boundary_trips_at_exact_limit() -> None:
    """경계: -10 == -(10% × 100) 도 트립한다('이하')."""
    d = evaluate(
        starting_capital=Decimal("100"),
        realized_pnl_today=Decimal("-10"),
        current_equity=Decimal("100"),
        limits=BreakerLimits.from_caps(_caps()),
    )
    assert d.tripped is True
    assert d.breached == ["daily_loss"]


def test_drawdown_trips() -> None:
    d = evaluate(
        starting_capital=Decimal("100"),
        realized_pnl_today=Decimal("-2"),
        current_equity=Decimal("80"),  # floor = 80, <= → trip
        limits=BreakerLimits.from_caps(_caps()),
    )
    assert d.tripped is True
    assert d.breached == ["total_drawdown"]


def test_both_limits_trip() -> None:
    d = evaluate(
        starting_capital=Decimal("100"),
        realized_pnl_today=Decimal("-50"),
        current_equity=Decimal("40"),
        limits=BreakerLimits.from_caps(_caps()),
    )
    assert d.tripped is True
    assert d.breached == ["daily_loss", "total_drawdown"]


def test_within_limits_no_trip() -> None:
    d = evaluate(
        starting_capital=Decimal("100"),
        realized_pnl_today=Decimal("-5"),
        current_equity=Decimal("95"),
        limits=BreakerLimits.from_caps(_caps()),
    )
    assert d.tripped is False
    assert d.breached == []


def test_disabled_never_trips() -> None:
    d = evaluate(
        starting_capital=Decimal("100"),
        realized_pnl_today=Decimal("-99"),
        current_equity=Decimal("1"),
        limits=BreakerLimits.from_caps(_caps(enabled=False)),
    )
    assert d.tripped is False
    assert "disabled" in d.reason


def test_zero_capital_not_evaluable() -> None:
    d = evaluate(
        starting_capital=Decimal("0"),
        realized_pnl_today=Decimal("-5"),
        current_equity=Decimal("-5"),
        limits=BreakerLimits.from_caps(_caps()),
    )
    assert d.tripped is False


def test_deterministic_same_input_same_decision() -> None:
    args = dict(
        starting_capital=Decimal("100"),
        realized_pnl_today=Decimal("-12"),
        current_equity=Decimal("70"),
        limits=BreakerLimits.from_caps(_caps()),
    )
    a = evaluate(**args)
    b = evaluate(**args)
    assert (a.tripped, a.breached, a.reason) == (b.tripped, b.breached, b.reason)


# ----------------------------------------------- T005: evaluate_from_audit


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def _paper_fill(conn, *, symbol, side, qty, price, ts, sid):
    audit.append(
        conn,
        OrderPaperFilledPayload(
            rule_id="R",
            symbol=symbol,
            side=side,
            qty=qty,
            simulated_fill_price_usd=price,
            quote_source="ask",
            correlation_id=f"{symbol}-{side}-{ts}",
            paper_session_id=sid,
        ),
        rule_id="R",
        symbol=symbol,
        correlation_id=f"{symbol}-{side}-{ts}",
        ts_utc=ts,
    )


def test_from_audit_daily_realized_loss_trips(conn) -> None:
    """오늘 매수 100 → 매도 80, 손실 -20 < -10 한도 → 트립."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-26T00:00:00.000Z", host="t",
        ),
    )
    _paper_fill(conn, symbol="AAPL", side="BUY", qty=1, price="100",
                ts="2026-05-26T10:00:00.000Z", sid=sid)
    _paper_fill(conn, symbol="AAPL", side="SELL", qty=1, price="80",
                ts="2026-05-26T11:00:00.000Z", sid=sid)
    d = evaluate_from_audit(
        conn, mode="paper", starting_capital=Decimal("100"), caps=_caps(), now=NOW
    )
    assert d.tripped is True
    assert "daily_loss" in d.breached


def test_from_audit_uses_full_history_for_cost_basis(conn) -> None:
    """어제 산 주식을 오늘 손실 매도해도 원가 기준이 정확(전체 시퀀스 재구성)."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-25T00:00:00.000Z", host="t",
        ),
    )
    # 어제 매수 100
    _paper_fill(conn, symbol="AAPL", side="BUY", qty=1, price="100",
                ts="2026-05-25T10:00:00.000Z", sid=sid)
    # 오늘 매도 80 → 오늘 실현 -20
    _paper_fill(conn, symbol="AAPL", side="SELL", qty=1, price="80",
                ts="2026-05-26T11:00:00.000Z", sid=sid)
    d = evaluate_from_audit(
        conn, mode="paper", starting_capital=Decimal("100"), caps=_caps(), now=NOW
    )
    assert d.tripped is True
    assert "daily_loss" in d.breached


def test_from_audit_yesterday_loss_not_counted_today(conn) -> None:
    """어제 실현된 손실은 '오늘 손실' 한도에 포함되지 않는다."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-25T00:00:00.000Z", host="t",
        ),
    )
    _paper_fill(conn, symbol="AAPL", side="BUY", qty=1, price="100",
                ts="2026-05-25T10:00:00.000Z", sid=sid)
    _paper_fill(conn, symbol="AAPL", side="SELL", qty=1, price="80",
                ts="2026-05-25T11:00:00.000Z", sid=sid)
    # 낙폭 한도는 넉넉히(어제 손실로 자산 80, floor 80 → 경계라 트립할 수 있으니 dd 30%)
    d = evaluate_from_audit(
        conn, mode="paper", starting_capital=Decimal("100"),
        caps=_caps(drawdown="30"), now=NOW,
    )
    assert "daily_loss" not in d.breached


def test_from_audit_drawdown_via_marks(conn) -> None:
    """미실현 손실(시세 하락)로 자산 floor 붕괴 → 낙폭 트립."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-26T00:00:00.000Z", host="t",
        ),
    )
    # 100×1 매수, 보유 중. 시세 50 → 미실현 -50 → 자산 50 <= floor 80
    _paper_fill(conn, symbol="AAPL", side="BUY", qty=1, price="100",
                ts="2026-05-26T10:00:00.000Z", sid=sid)
    d = evaluate_from_audit(
        conn, mode="paper", starting_capital=Decimal("100"), caps=_caps(),
        now=NOW, marks={"AAPL": Decimal("50")},
    )
    assert d.tripped is True
    assert "total_drawdown" in d.breached


def test_from_audit_missing_mark_conservative(conn) -> None:
    """시세 결측이면 미실현 0 → 실현 손실 없으면 트립 안 함(오트립 방지)."""
    sid = audit.append(
        conn,
        PaperRunStartedPayload(
            pid=1, config_path="/x", ruleset_sha256="a" * 64,
            started_at_utc="2026-05-26T00:00:00.000Z", host="t",
        ),
    )
    _paper_fill(conn, symbol="AAPL", side="BUY", qty=1, price="100",
                ts="2026-05-26T10:00:00.000Z", sid=sid)
    d = evaluate_from_audit(
        conn, mode="paper", starting_capital=Decimal("100"), caps=_caps(),
        now=NOW, marks={},  # 시세 없음
    )
    assert d.tripped is False
    assert d.metadata.get("unmarked_symbols") == "AAPL"


def test_from_audit_no_trades_no_trip(conn) -> None:
    d = evaluate_from_audit(
        conn, mode="paper", starting_capital=Decimal("100"), caps=_caps(), now=NOW
    )
    assert d.tripped is False


# --------------------------------------------------------- T007: audit payload


def test_circuit_breaker_payload_roundtrip(conn) -> None:
    seq = audit.append(
        conn,
        CircuitBreakerTrippedPayload(
            mode="paper",
            tripped_at_utc="2026-05-26T11:00:00.000Z",
            starting_capital_usd="100",
            realized_pnl_today_usd="-20",
            current_equity_usd="80",
            breached=["daily_loss"],
            daily_loss_limit_pct="10",
            max_total_drawdown_pct="20",
            reason="circuit breaker tripped: daily realized loss",
        ),
    )
    assert seq > 0
    rows = audit.read_all(conn)
    row = [r for r in rows if r["event_type"] == "CIRCUIT_BREAKER_TRIPPED"][0]
    payload = audit.parse_payload(row)
    assert payload["mode"] == "paper"
    assert payload["breached"] == ["daily_loss"]
    assert payload["realized_pnl_today_usd"] == "-20"
