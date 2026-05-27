"""Unit tests for the pure fill-ingestion planner (spec 015, T005)."""

from __future__ import annotations

from decimal import Decimal

from auto_invest.broker.models import BrokerExecution
from auto_invest.execution.fill_sync import OpenOrder, plan_fill_ingestion


def _order(
    *,
    corr: str = "ord-1",
    kis: str = "K1",
    symbol: str = "AAPL",
    side: str = "BUY",
    qty: int = 100,
    state: str = "SUBMITTED",
) -> OpenOrder:
    return OpenOrder(
        correlation_id=corr,
        kis_order_id=kis,
        symbol=symbol,
        side=side,
        rule_id="r1",
        ordered_qty=qty,
        state=state,
    )


def _exec(
    *,
    kis: str = "K1",
    symbol: str = "AAPL",
    filled: int = 100,
    price: str = "150",
    terminal: bool = False,
) -> BrokerExecution:
    return BrokerExecution(
        kis_order_id=kis,
        symbol=symbol,
        filled_qty=filled,
        avg_fill_price_usd=Decimal(price),
        terminal=terminal,
    )


def test_full_fill_plans_one_fill_and_filled_transition() -> None:
    plan = plan_fill_ingestion([_order()], [_exec(filled=100)], {})
    assert len(plan.fills) == 1
    f = plan.fills[0]
    assert f.qty == 100
    assert f.price_usd == Decimal("150")
    assert f.kis_fill_id == "K1:100"
    assert len(plan.transitions) == 1
    assert plan.transitions[0].to_state == "FILLED"
    assert plan.transitions[0].from_state == "SUBMITTED"


def test_partial_fill_plans_partial_state() -> None:
    plan = plan_fill_ingestion([_order(qty=100)], [_exec(filled=40)], {})
    assert plan.fills[0].qty == 40
    assert plan.fills[0].kis_fill_id == "K1:40"
    assert plan.transitions[0].to_state == "PARTIALLY_FILLED"


def test_incremental_only_records_delta() -> None:
    # 누적 70 인데 이미 40 기록 → 추가 30 만.
    order = _order(qty=100, state="PARTIALLY_FILLED")
    plan = plan_fill_ingestion([order], [_exec(filled=70)], {"ord-1": 40})
    assert len(plan.fills) == 1
    assert plan.fills[0].qty == 30
    assert plan.fills[0].kis_fill_id == "K1:70"
    # 이미 PARTIALLY_FILLED 상태였고 아직 미완 → 상태 전이는 없음(중복 전이 방지).
    assert plan.transitions == []


def test_idempotent_when_recorded_equals_broker() -> None:
    # 이미 100 기록 + 브로커 누적 100 → delta 0, 새 FILL 없음.
    order = _order(qty=100, state="FILLED")
    plan = plan_fill_ingestion([order], [_exec(filled=100)], {"ord-1": 100})
    assert plan.fills == []
    # 상태가 이미 FILLED 면 전이도 없음(중복 전이 방지).
    assert plan.transitions == []


def test_negative_delta_is_skipped_with_warning() -> None:
    # 브로커 누적 50 < 기 기록 80 (되돌림/이상치) → 기록 보류 + 경고.
    order = _order(qty=100, state="PARTIALLY_FILLED")
    plan = plan_fill_ingestion([order], [_exec(filled=50)], {"ord-1": 80})
    assert plan.fills == []
    assert any("되돌림" in w or "이상치" in w for w in plan.warnings)


def test_nonpositive_price_skips_fill_with_warning() -> None:
    order = _order(qty=100)
    plan = plan_fill_ingestion([order], [_exec(filled=10, price="0")], {})
    assert plan.fills == []
    assert any("비양수" in w for w in plan.warnings)


def test_terminal_partial_transitions_expired_with_cancel() -> None:
    # 부분 체결 후 브로커가 종료(취소/만료) 보고 → 잔여 미체결, EXPIRED + CANCEL.
    order = _order(qty=100, state="PARTIALLY_FILLED")
    plan = plan_fill_ingestion(
        [order], [_exec(filled=40, terminal=True)], {"ord-1": 40}
    )
    assert plan.fills == []  # 추가 체결 없음
    assert plan.transitions[0].to_state == "EXPIRED"
    assert plan.transitions[0].audit_cancel is True


def test_no_terminal_signal_keeps_order_open() -> None:
    # 체결 0 + 종료 신호 없음 → 추측으로 종료하지 않음(상태 무전이).
    order = _order(qty=100, state="SUBMITTED")
    plan = plan_fill_ingestion([order], [_exec(filled=0, terminal=False)], {})
    assert plan.fills == []
    assert plan.transitions == []


def test_order_not_reported_by_broker_no_change() -> None:
    # 브로커가 아직 이 주문을 보고하지 않음 → 변화 없음.
    order = _order(kis="K1")
    plan = plan_fill_ingestion([order], [_exec(kis="OTHER")], {})
    assert plan.fills == []
    assert plan.transitions == []


def test_sell_side_records_sell_fill() -> None:
    order = _order(side="SELL", qty=50, symbol="VOO")
    plan = plan_fill_ingestion(
        [order], [_exec(symbol="VOO", filled=50, price="500")], {}
    )
    assert plan.fills[0].side == "SELL"
    assert plan.fills[0].qty == 50
    assert plan.transitions[0].to_state == "FILLED"
