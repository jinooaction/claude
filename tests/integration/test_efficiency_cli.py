"""Integration tests for `auto-invest efficiency` (T401)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import db
from auto_invest.telemetry.store import TokenUsage, append_token_usage

runner = CliRunner()


def _u(ts: str, decision_class: str = "x", inp: int = 100) -> TokenUsage:
    return TokenUsage(
        model="claude-opus-4-7",
        decision_class=decision_class,
        input_tokens=inp,
        output_tokens=50,
        cache_read_tokens=300,
        cache_write_tokens=0,
        cost_usd="0.001000",
        latency_ms=500,
        error_class=None,
        correlation_id=ts,
        ts_utc=ts,
    )


def test_empty_db_returns_zero(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    result = runner.invoke(
        app,
        [
            "efficiency",
            "--db",
            str(db_path),
            "--window",
            "7d",
            "--as-of",
            "2026-05-06",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["call_count"] == 0
    assert payload["per_decision_class"] == {}
    assert payload["top_n_calls"] == []
    for kpi in payload["kpis"]:
        assert kpi["tier"] == "N/A"


def test_populated_db_returns_kpis(tmp_path: Path):
    db_path = tmp_path / "filled.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    append_token_usage(conn, _u("2026-05-04T10:00:00.000Z"))
    append_token_usage(conn, _u("2026-05-04T11:00:00.000Z"))
    conn.close()

    result = runner.invoke(
        app,
        [
            "efficiency",
            "--db",
            str(db_path),
            "--window",
            "7d",
            "--as-of",
            "2026-05-06",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["call_count"] == 2
    kpi_names = {k["name"] for k in payload["kpis"]}
    assert kpi_names == {
        "cache_hit_rate",
        "tokens_per_decision_p95",
        "usd_per_decision_mean",
        "latency_p95_ms",
    }


def test_emits_price_table_loaded_audit_row(tmp_path: Path):
    """T503: cli.efficiency must record one PRICE_TABLE_LOADED row per process,
    pinned to the loaded table's SHA-256 (price-table.md §Validation)."""
    db_path = tmp_path / "audit.db"
    result = runner.invoke(
        app,
        [
            "efficiency",
            "--db",
            str(db_path),
            "--window",
            "7d",
            "--as-of",
            "2026-05-06",
        ],
    )
    assert result.exit_code == 0, result.stdout

    conn = db.get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM audit_log WHERE event_type='PRICE_TABLE_LOADED'"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    payload = json.loads(rows[0]["payload_json"])
    assert payload["path"].endswith("llm_prices.toml")
    assert len(payload["sha256"]) == 64


def test_byte_stable_for_same_input(tmp_path: Path):
    db_path = tmp_path / "stable.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    append_token_usage(conn, _u("2026-05-04T10:00:00.000Z", "a"))
    append_token_usage(conn, _u("2026-05-04T11:00:00.000Z", "b"))
    conn.close()

    args = [
        "efficiency",
        "--db",
        str(db_path),
        "--window",
        "7d",
        "--as-of",
        "2026-05-06",
    ]
    a = runner.invoke(app, args).stdout
    b = runner.invoke(app, args).stdout
    assert a == b
