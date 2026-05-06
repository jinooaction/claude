"""Tests for `auto_invest.persistence.{db,audit}` (T013)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    FillPayload,
    HaltSetPayload,
    OrderIntentPayload,
    OrderRejectedByGatePayload,
    OrderSubmittedPayload,
    SecretsLoadedPayload,
    WorkerStartedPayload,
    WorkerStoppedPayload,
)


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    connection = db.get_connection(path)
    db.migrate(connection)
    yield connection
    connection.close()


# ------------------------------------------------------------ migrations


def test_migrate_creates_all_expected_tables(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r["name"] for r in rows}
    expected = {
        "audit_log",
        "current_positions",
        "fills",
        "order_state_history",
        "orders",
        "price_bars",
        "reconciliation_runs",
        "schema_migrations",
        "strategy_stage_history",
    }
    # sqlite_sequence is added by SQLite for tables with AUTOINCREMENT —
    # ignore it when checking our schema.
    assert expected.issubset(names)


def test_migrate_is_idempotent(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    first = db.migrate(c)
    second = db.migrate(c)
    # 0001 must be applied on the first call; second call must be a no-op.
    # Additional spec 002+ migrations may also appear in `first`.
    assert "0001_initial" in first
    assert second == []


def test_pending_migrations_reports_unapplied(tmp_path: Path):
    path = tmp_path / "test.db"
    c = db.get_connection(path)
    pending = db.pending_migrations(c)
    assert "0001_initial" in pending
    db.migrate(c)
    assert db.pending_migrations(c) == []


# ------------------------------------------------------------ append + seq


def test_append_returns_monotonic_seq(conn: sqlite3.Connection):
    a = audit.append(conn, WorkerStartedPayload(pid=1, config_path="x.toml"))
    b = audit.append(conn, WorkerStoppedPayload(reason="test"))
    c = audit.append(conn, HaltSetPayload(reason="ad-hoc"))
    assert (a, b, c) == (1, 2, 3)


def test_append_records_event_type_and_metadata(conn: sqlite3.Connection):
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r1",
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            qty=10,
            limit_price_usd="180.00",
        ),
        rule_id="r1",
        symbol="AAPL",
        correlation_id="ord-1",
    )
    row = conn.execute("SELECT * FROM audit_log").fetchone()
    assert row["event_type"] == "ORDER_INTENT"
    assert row["rule_id"] == "r1"
    assert row["symbol"] == "AAPL"
    assert row["correlation_id"] == "ord-1"
    assert row["ts_utc"].endswith("Z")


def test_append_payload_round_trips_through_json(conn: sqlite3.Connection):
    audit.append(
        conn,
        OrderRejectedByGatePayload(
            gate="per_trade_cap_gate",
            reason="qty * price exceeds 5%",
            metadata={"limit_pct": "5.0", "would_become_pct": "5.4"},
        ),
        rule_id="r1",
        symbol="AAPL",
    )
    [row] = audit.read_all(conn)
    payload = audit.parse_payload(row)
    assert payload["gate"] == "per_trade_cap_gate"
    assert payload["metadata"]["would_become_pct"] == "5.4"


# ------------------------------------------------------------ payload validation


def test_payload_rejects_extra_fields():
    with pytest.raises(ValidationError):
        OrderIntentPayload(
            rule_id="r1",
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            qty=10,
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_payload_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        FillPayload(qty=1, price_usd="1.0", executed_at_utc="2026-05-02T13:31:00Z")  # type: ignore[call-arg]


def test_payload_event_type_is_immutable():
    with pytest.raises(ValidationError):
        OrderSubmittedPayload(
            event_type="WORKER_STARTED",  # type: ignore[arg-type]
            kis_order_id="K1",
            submitted_at_utc="2026-05-02T13:31:00Z",
        )


def test_payload_is_frozen():
    payload = SecretsLoadedPayload(keys=["KIS_APP_KEY"])
    with pytest.raises(ValidationError):
        payload.keys = ["MUTATED"]  # type: ignore[misc]


# ------------------------------------------------------------ append-only invariant


def test_audit_log_refuses_update(conn: sqlite3.Connection):
    audit.append(conn, WorkerStartedPayload(pid=1, config_path="x.toml"))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET event_type='HACKED'")


def test_audit_log_refuses_delete(conn: sqlite3.Connection):
    audit.append(conn, WorkerStartedPayload(pid=1, config_path="x.toml"))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_log")


def test_other_append_only_tables_refuse_update(conn: sqlite3.Connection):
    # seed a row in each protected table directly (production code uses
    # higher-level writers added in later phases).
    conn.execute(
        "INSERT INTO order_state_history (order_correlation_id, to_state, ts_utc) "
        "VALUES ('ord-1', 'INTENT', '2026-05-02T13:31:00.000Z')"
    )
    conn.execute(
        "INSERT INTO fills (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc) "
        "VALUES ('ord-1', 'F1', 1, '180.00', '2026-05-02T13:31:00.000Z')"
    )
    conn.execute(
        "INSERT INTO strategy_stage_history (rule_id, to_stage, ts_utc) "
        "VALUES ('r1', 'CANARY', '2026-05-02T13:31:00.000Z')"
    )

    update_attempts = {
        "order_state_history": "UPDATE order_state_history SET to_state='HACKED'",
        "fills": "UPDATE fills SET price_usd='999.99'",
        "strategy_stage_history": "UPDATE strategy_stage_history SET to_stage='HACKED'",
    }
    for table, statement in update_attempts.items():
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(statement)
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(f"DELETE FROM {table}")


# ------------------------------------------------------------ correlation linkage


def test_correlation_id_links_lifecycle(conn: sqlite3.Connection):
    cid = "ord-42"
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r1",
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            qty=5,
            limit_price_usd="180.00",
        ),
        rule_id="r1",
        symbol="AAPL",
        correlation_id=cid,
    )
    audit.append(
        conn,
        OrderSubmittedPayload(
            kis_order_id="K1",
            submitted_at_utc="2026-05-02T13:31:00.000Z",
        ),
        rule_id="r1",
        symbol="AAPL",
        correlation_id=cid,
    )
    audit.append(
        conn,
        FillPayload(
            kis_fill_id="F1",
            qty=5,
            price_usd="180.00",
            executed_at_utc="2026-05-02T13:31:01.000Z",
        ),
        rule_id="r1",
        symbol="AAPL",
        correlation_id=cid,
    )

    rows = audit.read_by_correlation(conn, cid)
    assert [r["event_type"] for r in rows] == [
        "ORDER_INTENT",
        "ORDER_SUBMITTED",
        "FILL",
    ]
    assert all(r["correlation_id"] == cid for r in rows)


# ------------------------------------------------------------ orders constraints


def test_orders_check_constraints(conn: sqlite3.Connection):
    # qty > 0
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO orders (correlation_id, rule_id, symbol, side, order_type, qty, state) "
            "VALUES ('c1','r1','AAPL','BUY','LIMIT',0,'INTENT')"
        )
    # side enum
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO orders (correlation_id, rule_id, symbol, side, order_type, qty, state) "
            "VALUES ('c2','r1','AAPL','HODL','LIMIT',1,'INTENT')"
        )
    # order_type enum
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO orders (correlation_id, rule_id, symbol, side, order_type, qty, state) "
            "VALUES ('c3','r1','AAPL','BUY','GTD',1,'INTENT')"
        )


def test_audit_log_payload_is_valid_json(conn: sqlite3.Connection):
    audit.append(conn, HaltSetPayload(reason="lunch"))
    [row] = audit.read_all(conn)
    parsed = json.loads(row["payload_json"])
    assert parsed["event_type"] == "HALT_SET"
    assert parsed["reason"] == "lunch"
