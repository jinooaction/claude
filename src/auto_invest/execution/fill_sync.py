"""Live fill ingestion (spec 015) — 라이브 체결 동기화.

브로커가 접수만 확인해 준 `SUBMITTED` 주문이 **실제로 체결됐는지**를 다시 조회해
시스템 장부에 반영하는 마지막 고리. 주문을 내거나 취소하지 않는다 — 브로커가
확인한 체결 사실만 멱등하게 기록한다.

설계:
  - `plan_fill_ingestion`  — 순수 함수. (열린 주문, 브로커 체결, 이미 기록된 양)
                             → 적용할 FILL + 상태 전이 계획. 브로커/DB 미접근이라
                             결정론적으로 테스트 가능(FR-007).
  - `sync_fills`           — 얇은 async 오케스트레이터. 열린 주문 로드 → 브로커
                             체결 조회 → plan → 적용(FILL 감사 + fills INSERT +
                             보유 캐시 갱신 + 상태 전이). 오류는 격리(거래 무중단).

멱등성: `kis_fill_id = "{kis_order_id}:{누적체결량}"` 라 같은 누적 상태 재폴링은
같은 키 → `fills` UNIQUE 충돌 무시. 게다가 이미 기록된 양만큼 delta 가 0 이 되어
새 FILL 자체가 계획되지 않는다(이중 안전).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.models import BrokerExecution
from auto_invest.broker.overseas import get_order_executions
from auto_invest.config.enums import Side
from auto_invest.execution.order_router import _record_transition, _utcnow_iso_ms
from auto_invest.persistence import audit
from auto_invest.persistence import positions as positions_mod
from auto_invest.persistence.audit import CancelPayload, ErrorPayload, FillPayload

logger = logging.getLogger(__name__)

_OPEN_STATES = ("SUBMITTED", "PARTIALLY_FILLED")


@dataclass(frozen=True)
class OpenOrder:
    """체결 동기화 대상인 로컬 열린 주문 한 건."""

    correlation_id: str
    kis_order_id: str
    symbol: str
    side: str  # "BUY" | "SELL"
    rule_id: str
    ordered_qty: int
    state: str


@dataclass(frozen=True)
class PlannedFill:
    """적용할 체결 한 건(누적 대비 추가분)."""

    correlation_id: str
    kis_order_id: str
    symbol: str
    side: str
    rule_id: str
    qty: int
    price_usd: Decimal
    kis_fill_id: str


@dataclass(frozen=True)
class PlannedTransition:
    """적용할 주문 상태 전이 한 건. `audit_cancel`이면 CANCEL 감사도 남긴다."""

    correlation_id: str
    from_state: str
    to_state: str
    reason: str
    audit_cancel: bool = False


@dataclass(frozen=True)
class FillPlan:
    fills: list[PlannedFill] = field(default_factory=list)
    transitions: list[PlannedTransition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FillSyncResult:
    """동기화 결과 요약(CLI·테스트·로그용)."""

    polled: bool  # 브로커를 실제로 호출했는지(열린 주문 0건이면 False)
    open_orders: int
    fills_applied: int
    qty_applied: int
    transitions: int
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def plan_fill_ingestion(
    open_orders: list[OpenOrder],
    executions: list[BrokerExecution],
    recorded_qty_by_corr: dict[str, int],
) -> FillPlan:
    """순수 계획 함수 — 부수효과 없음(FR-007).

    각 열린 주문에 대해 브로커 누적 체결량과 이미 기록된 양의 차이만큼 FILL 을
    계획하고, 누적 체결량/종료 여부로 상태 전이를 계획한다."""
    by_order: dict[str, BrokerExecution] = {e.kis_order_id: e for e in executions}
    plan = FillPlan()

    for order in open_orders:
        execution = by_order.get(order.kis_order_id)
        if execution is None:
            continue  # 브로커가 아직 이 주문을 보고하지 않음 → 변화 없음.

        broker_filled = execution.filled_qty
        recorded = recorded_qty_by_corr.get(order.correlation_id, 0)
        delta = broker_filled - recorded

        if delta < 0:
            plan.warnings.append(
                f"{order.correlation_id}: 브로커 누적 체결 {broker_filled} < "
                f"기 기록 {recorded} — 되돌림/이상치, 기록 보류"
            )
        elif delta > 0:
            price = execution.avg_fill_price_usd
            if price <= 0:
                plan.warnings.append(
                    f"{order.correlation_id}: 체결가 {price} 비양수 — FILL 보류"
                )
            else:
                # delta 는 cumulative 평균 체결가로 기록한다. 한 주문이 짧은 시간에
                # 비슷한 가격으로 채워지는 일반적인 경우 정확하며, 누적량 기반
                # kis_fill_id 로 멱등이 보장된다.
                plan.fills.append(
                    PlannedFill(
                        correlation_id=order.correlation_id,
                        kis_order_id=order.kis_order_id,
                        symbol=order.symbol,
                        side=order.side,
                        rule_id=order.rule_id,
                        qty=delta,
                        price_usd=price,
                        kis_fill_id=f"{order.kis_order_id}:{broker_filled}",
                    )
                )

        # 상태 전이: 누적 체결량 기준(브로커가 진실).
        to_state: str | None = None
        audit_cancel = False
        reason = ""
        if broker_filled >= order.ordered_qty:
            to_state = "FILLED"
            reason = f"filled {broker_filled}/{order.ordered_qty}"
        elif execution.terminal and broker_filled < order.ordered_qty:
            to_state = "EXPIRED"
            audit_cancel = True
            reason = (
                f"broker terminal, filled {broker_filled}/{order.ordered_qty}"
            )
        elif broker_filled > 0:
            to_state = "PARTIALLY_FILLED"
            reason = f"partial {broker_filled}/{order.ordered_qty}"

        if to_state is not None and to_state != order.state:
            plan.transitions.append(
                PlannedTransition(
                    correlation_id=order.correlation_id,
                    from_state=order.state,
                    to_state=to_state,
                    reason=reason,
                    audit_cancel=audit_cancel,
                )
            )

    return plan


def _load_open_orders(conn: sqlite3.Connection) -> list[OpenOrder]:
    placeholders = ",".join("?" for _ in _OPEN_STATES)
    rows = conn.execute(
        f"""
        SELECT correlation_id, kis_order_id, symbol, side, rule_id, qty, state
        FROM orders
        WHERE state IN ({placeholders}) AND kis_order_id IS NOT NULL
        """,
        _OPEN_STATES,
    ).fetchall()
    return [
        OpenOrder(
            correlation_id=r["correlation_id"],
            kis_order_id=r["kis_order_id"],
            symbol=r["symbol"],
            side=r["side"],
            rule_id=r["rule_id"],
            ordered_qty=int(r["qty"]),
            state=r["state"],
        )
        for r in rows
    ]


def _recorded_qty_by_corr(
    conn: sqlite3.Connection, correlation_ids: list[str]
) -> dict[str, int]:
    if not correlation_ids:
        return {}
    placeholders = ",".join("?" for _ in correlation_ids)
    rows = conn.execute(
        f"""
        SELECT order_correlation_id AS corr, COALESCE(SUM(qty), 0) AS total
        FROM fills
        WHERE order_correlation_id IN ({placeholders})
        GROUP BY order_correlation_id
        """,
        correlation_ids,
    ).fetchall()
    return {r["corr"]: int(r["total"]) for r in rows}


def _apply_fill(conn: sqlite3.Connection, fill: PlannedFill, ts_iso: str) -> None:
    """한 FILL 적용: 감사 이벤트 + fills row(멱등) + 보유 캐시 갱신."""
    audit.append(
        conn,
        FillPayload(
            kis_fill_id=fill.kis_fill_id,
            qty=fill.qty,
            price_usd=str(fill.price_usd),
            executed_at_utc=ts_iso,
        ),
        rule_id=fill.rule_id,
        symbol=fill.symbol,
        correlation_id=fill.correlation_id,
        ts_utc=ts_iso,
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO fills
            (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc)
        VALUES (?, ?, ?, ?, ?)
        """,
        (fill.correlation_id, fill.kis_fill_id, fill.qty, str(fill.price_usd), ts_iso),
    )
    positions_mod.update_from_fill(
        conn,
        symbol=fill.symbol,
        side=Side(fill.side),
        qty=fill.qty,
        price_usd=fill.price_usd,
        ts_utc=ts_iso,
    )


def _iso_ms(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def apply_fill_plan(
    conn: sqlite3.Connection, plan: FillPlan, *, ts_iso: str | None = None
) -> tuple[int, int, int]:
    """계획을 DB에 적용한다. (적용된 FILL 수, 적용 수량 합, 전이 수) 반환.

    `ts_iso` 는 체결·전이의 기록 시각이다. 워커가 틱의 논리적 시각을 넘겨
    감사 로그 시각이 결정론적이게 한다(미지정 시 현재 UTC)."""
    ts_iso = ts_iso or _utcnow_iso_ms()
    qty_applied = 0
    for fill in plan.fills:
        _apply_fill(conn, fill, ts_iso)
        qty_applied += fill.qty
    for tr in plan.transitions:
        _record_transition(conn, tr.correlation_id, tr.from_state, tr.to_state, tr.reason)
        if tr.audit_cancel:
            audit.append(
                conn,
                CancelPayload(reason=tr.reason),
                correlation_id=tr.correlation_id,
            )
    return len(plan.fills), qty_applied, len(plan.transitions)


async def sync_fills(
    conn: sqlite3.Connection,
    broker: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    market: str = "NASD",
    now: datetime | None = None,
) -> FillSyncResult:
    """라이브 열린 주문의 체결을 브로커에서 당겨와 장부에 반영한다(읽기-기반 적재).

    열린 주문이 0건이면 브로커를 호출하지 않는다(불필요 API 절약). 브로커 호출
    실패 등 어떤 예외도 ERROR 감사를 남기고 삼켜서 호출자(워커 틱)의 거래 루프를
    멈추지 않는다(FR-009, SC-005)."""
    moment = now or datetime.now(UTC)
    open_orders = _load_open_orders(conn)
    if not open_orders:
        return FillSyncResult(
            polled=False, open_orders=0, fills_applied=0, qty_applied=0, transitions=0
        )

    try:
        executions = await get_order_executions(
            broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account,
            order_date_yyyymmdd=moment.strftime("%Y%m%d"),
            market=market,
        )
    except Exception as exc:  # noqa: BLE001 — 거래 무중단: 격리해 ERROR 로 기록.
        audit.append(
            conn,
            ErrorPayload(
                where="fill_sync",
                message=str(exc),
                exc_type=type(exc).__name__,
            ),
        )
        logger.warning("fill sync broker call failed: %s", exc)
        return FillSyncResult(
            polled=True,
            open_orders=len(open_orders),
            fills_applied=0,
            qty_applied=0,
            transitions=0,
            error=str(exc),
        )

    recorded = _recorded_qty_by_corr(conn, [o.correlation_id for o in open_orders])
    plan = plan_fill_ingestion(open_orders, executions, recorded)
    fills_applied, qty_applied, transitions = apply_fill_plan(
        conn, plan, ts_iso=_iso_ms(moment)
    )

    for w in plan.warnings:
        audit.append(conn, ErrorPayload(where="fill_sync", message=w))

    return FillSyncResult(
        polled=True,
        open_orders=len(open_orders),
        fills_applied=fills_applied,
        qty_applied=qty_applied,
        transitions=transitions,
        warnings=plan.warnings,
    )
