"""Durable, at-most-once cancel request; final status belongs to fill_sync."""
from __future__ import annotations

from auto_invest.execution.authority import ExecutionAuthority
from auto_invest.persistence import audit


async def request_cancellation(
    authority: ExecutionAuthority, *, correlation_id: str, market: str, reason: str
) -> str:
    conn = authority.conn
    row = conn.execute("SELECT * FROM orders WHERE correlation_id=?",
                       (correlation_id,)).fetchone()
    if row is None or row["state"] not in {"SUBMITTED", "PARTIALLY_FILLED"}:
        return "NOT_OPEN"
    claimed = False

    def claim():
        nonlocal claimed
        # This executes AFTER the account/deploy locks and final open-order
        # checks, but BEFORE the network write. Contention consumes no attempt.
        conn.execute("BEGIN IMMEDIATE")
        try:
            prior = conn.execute(
                "SELECT 1 FROM audit_log WHERE event_type='ORDER_CANCEL_REQUEST' "
                "AND correlation_id=? LIMIT 1", (correlation_id,)).fetchone()
            if prior:
                conn.commit()
                return False
            audit.append(
                conn, audit.OrderCancelRequestPayload(
                    phase="REQUESTED", reason=reason, kis_order_id=row["kis_order_id"]),
                correlation_id=correlation_id, rule_id=row["rule_id"], symbol=row["symbol"])
            conn.commit()
            claimed = True
            return True
        except BaseException:
            conn.rollback()
            raise

    phase = "ACKNOWLEDGED"
    try:
        sent = await authority.cancel_broker_order(
            kis_order_id=row["kis_order_id"], market=market, before_write=claim)
        if not sent:
            return "WAIT_BROKER_CONFIRMATION"
    except Exception:
        if not claimed:
            return "DEFERRED_BEFORE_WRITE"
        phase = "UNCERTAIN"
    audit.append(conn, audit.OrderCancelRequestPayload(
        phase=phase, reason=reason, kis_order_id=row["kis_order_id"]),
        correlation_id=correlation_id, rule_id=row["rule_id"], symbol=row["symbol"])
    return phase
