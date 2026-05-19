"""Spec 009 T021 — paper-run 가상 포지션 derived view.

`ORDER_PAPER_FILLED` 이벤트의 누적으로 계산되는 가상 포지션. 별도 테이블 없음 —
호출마다 audit_log에서 재집계 (research.md R-P3).

- BUY: 가중평균으로 avg_cost 갱신, qty += 매수량.
- SELL: realized_pnl += (sell_price - avg_cost) × sell_qty, qty -= 매도량.

`audit_log` 외 다른 테이블을 읽지 않음. PRAGMA query_only가 켜진 connection에서도
동작.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class VirtualPositionRow:
    """한 종목의 paper-run 누적 포지션."""

    symbol: str
    qty: int
    avg_cost_usd: Decimal
    realized_pnl_usd: Decimal
    last_event_at: str | None  # ISO8601, audit_log.ts_utc
    last_fill_price_usd: Decimal | None  # paper-report의 미실현 손익 추정에 사용


def recompute_virtual_positions(
    conn: sqlite3.Connection,
    *,
    paper_session_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, VirtualPositionRow]:
    """Paper 모드 가상 포지션을 audit_log에서 재계산해 종목별 dict로 리턴.

    - `paper_session_id`: 특정 세션의 fill만 합산. None이면 모든 세션 합산.
    - `since`/`until`: created_at 범위 필터. None이면 전 기간.
    """
    query = (
        "SELECT ts_utc, payload_json FROM audit_log "
        "WHERE event_type = 'ORDER_PAPER_FILLED'"
    )
    params: list[object] = []
    if since is not None:
        query += " AND ts_utc >= ?"
        params.append(since.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    if until is not None:
        query += " AND ts_utc < ?"
        params.append(until.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    query += " ORDER BY seq"

    positions: dict[str, VirtualPositionRow] = {}
    for row in conn.execute(query, params):
        payload = json.loads(row["payload_json"])
        if paper_session_id is not None and payload.get("paper_session_id") != paper_session_id:
            continue
        _apply_fill(
            positions,
            symbol=payload["symbol"],
            side=payload["side"],
            qty=int(payload["qty"]),
            fill_price=Decimal(payload["simulated_fill_price_usd"]),
            ts_utc=row["ts_utc"],
        )
    return positions


def _apply_fill(
    positions: dict[str, VirtualPositionRow],
    *,
    symbol: str,
    side: str,
    qty: int,
    fill_price: Decimal,
    ts_utc: str,
) -> None:
    pos = positions.get(symbol)
    if pos is None:
        pos = VirtualPositionRow(
            symbol=symbol,
            qty=0,
            avg_cost_usd=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            last_event_at=None,
            last_fill_price_usd=None,
        )
    if side == "BUY":
        old_total_cost = pos.avg_cost_usd * Decimal(pos.qty)
        new_total_cost = old_total_cost + fill_price * Decimal(qty)
        new_qty = pos.qty + qty
        new_avg = new_total_cost / Decimal(new_qty) if new_qty != 0 else Decimal("0")
        pos = VirtualPositionRow(
            symbol=symbol,
            qty=new_qty,
            avg_cost_usd=new_avg,
            realized_pnl_usd=pos.realized_pnl_usd,
            last_event_at=ts_utc,
            last_fill_price_usd=fill_price,
        )
    elif side == "SELL":
        realized = (fill_price - pos.avg_cost_usd) * Decimal(qty)
        pos = VirtualPositionRow(
            symbol=symbol,
            qty=pos.qty - qty,
            avg_cost_usd=pos.avg_cost_usd,  # 평균단가는 SELL에서 유지
            realized_pnl_usd=pos.realized_pnl_usd + realized,
            last_event_at=ts_utc,
            last_fill_price_usd=fill_price,
        )
    positions[symbol] = pos
