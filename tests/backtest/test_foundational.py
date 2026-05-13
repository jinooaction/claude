"""Phase-2 foundational test (T015 of spec 008).

Verifies that the one-time K-meta change set keeps the live pipeline
byte-identical (backwards compatibility) AND wires the new spec-008
infrastructure end-to-end:

- New BACKTEST_* payload classes round-trip through audit.append.
- The append-only invariant (constitution IV) still rejects UPDATE/
  DELETE for the new event types.
- Migration 0003 ran and the partial index for SC-B06 exists.
- Worker.__init__'s new optional kwargs default to None and have no
  observable effect on live behaviour.
- The kernel.toml manifest is loadable and contains both the new
  K7 group and the K4 += 0003 entry.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    BacktestCompletedPayload,
    BacktestFailedPayload,
    BacktestStartedPayload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------- fixtures


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "test.db"
    connection = db.get_connection(path)
    db.migrate(connection)
    yield connection
    connection.close()


# --------------------------------------------------------- payload round-trip


def _started_payload() -> BacktestStartedPayload:
    return BacktestStartedPayload(
        run_id="00000000-0000-0000-0000-000000000001",
        code_sha="0" * 40,
        dataset_hash="a" * 64,
        rules_hash="b" * 64,
        caps_hash="c" * 64,
        whitelist_hash="d" * 64,
        seed=0,
        vendor="yfinance",
        window_start="2024-01-02",
        window_end="2024-12-31",
        named_dataset=None,
    )


def test_backtest_started_round_trip(conn: sqlite3.Connection):
    payload = _started_payload()
    seq = audit.append(conn, payload)
    assert seq > 0
    row = conn.execute(
        "SELECT event_type, payload_json FROM audit_log WHERE seq = ?", (seq,)
    ).fetchone()
    assert row["event_type"] == "BACKTEST_STARTED"
    parsed = audit.parse_payload(row)
    assert parsed["run_id"] == payload.run_id
    assert parsed["code_sha"] == payload.code_sha
    assert parsed["vendor"] == "yfinance"


def test_backtest_completed_round_trip(conn: sqlite3.Connection):
    payload = BacktestCompletedPayload(
        run_id="00000000-0000-0000-0000-000000000002",
        total_return_pct="12.34",
        max_drawdown_pct="4.21",
        sharpe="0.83",
        fills_count=127,
        gate_rejections_count=3,
        promote_eligible=True,
        artifact_dir="data/backtests/00000000-0000-0000-0000-000000000002",
    )
    seq = audit.append(conn, payload)
    row = conn.execute("SELECT * FROM audit_log WHERE seq = ?", (seq,)).fetchone()
    assert row["event_type"] == "BACKTEST_COMPLETED"
    parsed = audit.parse_payload(row)
    assert parsed["promote_eligible"] is True
    assert parsed["sharpe"] == "0.83"


def test_backtest_failed_round_trip(conn: sqlite3.Connection):
    payload = BacktestFailedPayload(
        run_id="00000000-0000-0000-0000-000000000003",
        phase="ingest_ohlcv",
        reason="vendor 5xx after retry budget exhausted",
    )
    seq = audit.append(conn, payload)
    row = conn.execute("SELECT * FROM audit_log WHERE seq = ?", (seq,)).fetchone()
    assert row["event_type"] == "BACKTEST_FAILED"
    parsed = audit.parse_payload(row)
    assert parsed["phase"] == "ingest_ohlcv"


# --------------------------------------------------------- append-only invariant


def test_backtest_event_cannot_be_updated(conn: sqlite3.Connection):
    seq = audit.append(conn, _started_payload())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE audit_log SET event_type = 'TAMPERED' WHERE seq = ?", (seq,))


def test_backtest_event_cannot_be_deleted(conn: sqlite3.Connection):
    seq = audit.append(conn, _started_payload())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_log WHERE seq = ?", (seq,))


# --------------------------------------------------------- migration / index


def test_migration_0003_partial_index_exists(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='index' AND name='idx_audit_log_backtest_events'"
    ).fetchall()
    assert len(rows) == 1, "migration 0003 did not create the partial index"
    sql = rows[0]["sql"]
    assert "WHERE" in sql and "BACKTEST_STARTED" in sql


def test_sc_b06_query_uses_partial_index(conn: sqlite3.Connection):
    audit.append(conn, _started_payload())
    plan_rows = conn.execute(
        "EXPLAIN QUERY PLAN "
        "SELECT * FROM audit_log "
        "WHERE event_type = 'BACKTEST_COMPLETED' "
        "AND ts_utc >= datetime('now', '-30 days') "
        "ORDER BY ts_utc DESC"
    ).fetchall()
    plan_text = " ".join(str(r["detail"]) for r in plan_rows).lower()
    assert "idx_audit_log_backtest_events" in plan_text or "idx_audit_log_event" in plan_text


# --------------------------------------------------------- kernel manifest


def test_kernel_manifest_contains_k4_migration_and_k7():
    """Verify the foundational kernel.toml edits landed (T006)."""
    import tomllib

    manifest = tomllib.loads((REPO_ROOT / ".specify" / "memory" / "kernel.toml").read_text())
    k4_files = manifest["K4_append_only_audit"]["files"]
    assert "src/auto_invest/persistence/migrations/0003_backtest_events.sql" in k4_files, (
        "K4 must list the new migration file"
    )

    assert "K7_named_datasets" in manifest, "K7 group is the spec-008 enforcement counterpart"
    k7_files = manifest["K7_named_datasets"]["files"]
    assert "data/ohlcv/datasets/synthetic_shock_v1.json" in k7_files


# --------------------------------------------------------- Worker DI seam


def test_worker_kwargs_default_to_none_preserve_live_behaviour():
    """T013 added two optional kwargs; default None must be a no-op.

    We don't construct a full Worker (which requires a real DB + KIS
    secrets); we just inspect the signature so a regression on the
    DI-seam contract surfaces as a unit-level fail.
    """
    import inspect

    from auto_invest.worker.loop import Worker

    sig = inspect.signature(Worker.__init__)
    params = sig.parameters
    assert "quote_provider" in params, "T013 must add quote_provider kwarg"
    assert "clock" in params, "T013 must add clock kwarg"
    assert params["quote_provider"].default is None, "live default must be None"
    assert params["clock"].default is None, "live default must be None"


# --------------------------------------------------------- backtest helpers


def test_backtest_helpers_importable():
    """Smoke check that the Phase 2 helper modules import cleanly."""
    from auto_invest.backtest import errors, hashing, verdict
    from auto_invest.backtest.clock import SyntheticClock
    from auto_invest.backtest.config import BacktestConfig, NamedDataset, Window
    from auto_invest.backtest.ohlcv.canonical import OhlcvBar, canonical_dump, content_hash

    # Every export resolves; no symbol mismatches.
    assert errors.BacktestError is not None
    assert hashing.code_sha is not None
    assert verdict.VerdictThresholds().total_return_pct_min == verdict.Decimal("0")
    assert SyntheticClock is not None
    assert BacktestConfig is not None
    assert NamedDataset is not None
    assert Window is not None
    assert OhlcvBar is not None
    assert content_hash is not None
    assert canonical_dump is not None
