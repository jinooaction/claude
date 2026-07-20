from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.execution.execution_state import evaluate_execution_state
from auto_invest.persistence import db


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    return conn


def test_submission_unknown_buy_degrades_execution_state(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty,
             limit_price_usd, state)
        VALUES ('ord-unknown', 'r1', 'AAPL', 'BUY', 'LIMIT', 1,
                '100.00', 'SUBMISSION_UNKNOWN')
        """
    )

    state = evaluate_execution_state(conn)

    assert state.status == "DEGRADED_SELL_ONLY"
    assert [r.code for r in state.reasons] == ["submission_unknown_buy"]


def test_submission_unknown_sell_does_not_degrade_execution_state(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty,
             limit_price_usd, state)
        VALUES ('ord-unknown-sell', 'r1', 'AAPL', 'SELL', 'LIMIT', 1,
                '100.00', 'SUBMISSION_UNKNOWN')
        """
    )

    state = evaluate_execution_state(conn)

    assert state.status == "HEALTHY"
    assert state.reasons == ()


def test_latest_inconclusive_reconciliation_degrades_until_ok(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    conn.execute(
        """
        INSERT INTO reconciliation_runs
            (started_at_utc, finished_at_utc, result, mismatch_payload_json)
        VALUES ('2026-07-13T00:00:00.000Z', '2026-07-13T00:00:01.000Z',
                'INCONCLUSIVE', NULL)
        """
    )

    assert evaluate_execution_state(conn).status == "DEGRADED_SELL_ONLY"

    conn.execute(
        """
        INSERT INTO reconciliation_runs
            (started_at_utc, finished_at_utc, result, mismatch_payload_json)
        VALUES ('2026-07-13T00:05:00.000Z', '2026-07-13T00:05:01.000Z',
                'OK', NULL)
        """
    )

    state = evaluate_execution_state(conn)
    assert state.status == "HEALTHY"
    assert state.reasons == ()


def test_stale_buy_intent_degrades_execution_state(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty,
             limit_price_usd, state)
        VALUES ('ord-intent', 'r1', 'AAPL', 'BUY', 'LIMIT', 1,
                '100.00', 'INTENT')
        """
    )
    conn.execute(
        """
        INSERT INTO order_state_history
            (order_correlation_id, from_state, to_state, ts_utc, reason)
        VALUES ('ord-intent', NULL, 'INTENT', '2026-07-21T00:00:00.000Z', NULL)
        """
    )

    state = evaluate_execution_state(
        conn,
        now=datetime(2026, 7, 21, 0, 2, tzinfo=UTC),
        stale_after_seconds=60,
    )

    assert state.status == "DEGRADED_SELL_ONLY"
    assert "stale_pending_buy" in [r.code for r in state.reasons]


def test_current_intent_can_be_excluded_from_stale_check(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty,
             limit_price_usd, state)
        VALUES ('current-order', 'r1', 'AAPL', 'BUY', 'LIMIT', 1,
                '100.00', 'INTENT')
        """
    )
    conn.execute(
        """
        INSERT INTO order_state_history
            (order_correlation_id, from_state, to_state, ts_utc, reason)
        VALUES ('current-order', NULL, 'INTENT', '2026-07-21T00:00:00.000Z', NULL)
        """
    )

    state = evaluate_execution_state(
        conn,
        now=datetime(2026, 7, 21, 0, 2, tzinfo=UTC),
        stale_after_seconds=60,
        exclude_correlation_ids=("current-order",),
    )

    assert state.status == "HEALTHY"
