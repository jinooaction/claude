"""T008 — append-only invariants for the spec 002 tables.

Confirms that every new table introduced by 0002_data_and_backtest.sql
rejects UPDATE/DELETE while frozen = 1 (or unconditionally for the
non-frozen tables).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from auto_invest.persistence import db


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.get_connection(tmp_path / "test.db")
    db.migrate(c)
    yield c
    c.close()


def _insert_historical_bar(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO historical_bars
            (asset_class, venue, symbol, kind, vendor,
             bar_open_ts_utc, as_of_ts_utc,
             open, high, low, close, volume)
        VALUES ('equity','nasdaq','AAPL','ohlcv_1d','kis',
                '2024-01-02T00:00:00.000Z','2026-05-06T00:00:00.000Z',
                '185.0','188.0','183.0','187.0','1000000')
        """
    )


def test_historical_bars_blocks_update(conn: sqlite3.Connection) -> None:
    _insert_historical_bar(conn)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE historical_bars SET close='999' WHERE symbol='AAPL'")


def test_historical_bars_blocks_delete(conn: sqlite3.Connection) -> None:
    _insert_historical_bar(conn)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM historical_bars WHERE symbol='AAPL'")


def test_event_series_blocks_update(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO event_series
            (asset_class, venue, symbol, kind, vendor,
             event_ts_utc, as_of_ts_utc, payload_json)
        VALUES ('equity','nasdaq','AAPL','earnings_release','kis',
                '2024-02-01T20:00:00.000Z','2024-02-01T20:30:00.000Z',
                ?)
        """,
        (json.dumps({"eps": "1.50"}),),
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE event_series SET payload_json='{}' WHERE symbol='AAPL'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM event_series WHERE symbol='AAPL'")


def test_corporate_actions_blocks_mutation(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO corporate_actions
            (asset_class, venue, symbol, vendor, action_kind,
             effective_ts_utc, as_of_ts_utc, payload_json)
        VALUES ('equity','nasdaq','AAPL','kis','split',
                '2024-06-10T00:00:00.000Z','2024-06-09T00:00:00.000Z',
                ?)
        """,
        (json.dumps({"ratio_num": 2, "ratio_den": 1}),),
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE corporate_actions SET payload_json='{}' WHERE symbol='AAPL'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM corporate_actions WHERE symbol='AAPL'")


def test_data_quality_events_blocks_mutation(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO data_quality_events
            (event_ts_utc, asset_class, venue, symbol, kind, payload_json, severity)
        VALUES ('2024-01-02T00:00:00.000Z','equity','nasdaq','AAPL','gap',
                ?, 'block')
        """,
        (json.dumps({"missing_from": "...", "missing_to": "..."}),),
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE data_quality_events SET severity='info'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM data_quality_events")


def test_backtest_runs_blocks_mutation(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO backtest_runs
            (run_id, created_ts_utc, rule_snapshot_hash, config_hash,
             instruments_json, window_from_utc, window_to_utc,
             as_of_ts_pin_utc, mode, result_status)
        VALUES ('abc123', '2026-05-06T00:00:00.000Z', 'sha256:r', 'sha256:c',
                '[]', '2024-01-01T00:00:00.000Z','2025-01-01T00:00:00.000Z',
                '2026-05-06T00:00:00.000Z', 'single', 'succeeded')
        """,
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE backtest_runs SET result_status='failed'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM backtest_runs")


def test_promotion_seals_blocks_mutation(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO promotion_seals
            (seal_id, issued_ts_utc, rule_snapshot_hash,
             backtest_run_id, oos_metrics_json, thresholds_json)
        VALUES ('seal01','2026-05-06T00:00:00.000Z','sha256:r','run1','{}','{}')
        """,
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE promotion_seals SET revoked=1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM promotion_seals")


def test_divergence_events_blocks_mutation(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO divergence_events
            (event_ts_utc, seal_id, metric_kind, live_value,
             backtest_value, divergence_pct)
        VALUES ('2026-06-01T00:00:00.000Z','seal01','drawdown_pct','5.0','3.0','40.0')
        """,
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE divergence_events SET breached=1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM divergence_events")


def test_pending_migrations_after_apply(tmp_path: Path) -> None:
    c = db.get_connection(tmp_path / "test.db")
    db.migrate(c)
    assert db.pending_migrations(c) == []
