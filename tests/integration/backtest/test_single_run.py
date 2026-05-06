"""T030 + T031 — single backtest run + deterministic re-run."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.backtest.runner import execute_run
from auto_invest.config.data import DataSourcesConfig
from auto_invest.config.loader import load_config_for_backtest
from auto_invest.market_data.adapters import BarRecord, InstrumentRef
from auto_invest.market_data.historical_store import write_bars
from auto_invest.persistence import db


FIXTURE_RULE = Path("tests/fixtures/rules/aapl_rsi_demo.toml")
FIXTURE_BARS = Path("tests/fixtures/historical/equity/aapl_2024_2025_1d.jsonl")


def _ingest_fixture(conn: sqlite3.Connection) -> None:
    """Load the AAPL fixture into the historical store."""
    inst = InstrumentRef("equity", "nasdaq", "AAPL")
    records: list[BarRecord] = []
    for line in FIXTURE_BARS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        records.append(
            BarRecord(
                instrument=inst,
                kind=row["kind"],
                bar_open_ts_utc=_parse(row["bar_open_ts_utc"]),
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=Decimal(row["volume"]),
                is_adjusted=bool(row["is_adjusted"]),
            )
        )
    write_bars(
        conn, records, vendor="kis",
        as_of_ts=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _parse(text: str) -> datetime:
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _config_text(symbol: str = "AAPL") -> str:
    return f"""schema_version = "002.1"

[rule]
path = "tests/fixtures/rules/aapl_rsi_demo.toml"
snapshot_hash = "sha256:placeholder"

[window]
from_utc = "2024-01-01T00:00:00Z"
to_utc   = "2025-12-31T00:00:00Z"
as_of_ts_pin_utc = "2026-01-02T00:00:00Z"

[[instruments]]
asset_class = "equity"
venue       = "nasdaq"
symbol      = "{symbol}"
vendor      = "kis"

[mode]
kind = "single"

[runtime]
seed = 0
max_runtime_seconds = 600
"""


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    _ingest_fixture(c)
    yield c
    c.close()


def test_backtest_single_run_produces_report(conn: sqlite3.Connection, tmp_path: Path) -> None:
    cfg = load_config_for_backtest(FIXTURE_RULE)
    rule_text = FIXTURE_RULE.read_text(encoding="utf-8")
    config_text = _config_text()
    backtests_root = tmp_path / "backtests"

    run_dir, run_id = execute_run(
        conn=conn,
        config_text=config_text,
        rule_text=rule_text,
        rule=cfg.rules[0],
        data_sources=DataSourcesConfig(),
        whitelist=cfg.whitelist,
        caps=cfg.caps,
        starting_capital_usd=Decimal("10000"),
        backtests_root=backtests_root,
    )

    assert run_dir.exists()
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "report.md").exists()
    assert (run_dir / "audit_log.jsonl").exists()
    assert (run_dir / "orders.jsonl").exists()
    assert (run_dir / "inputs" / "run.toml").exists()
    assert (run_dir / "inputs" / "rule_snapshot.toml").exists()
    assert (run_dir / "inputs" / "data_pin.json").exists()

    metrics = json.loads((run_dir / "metrics.json").read_text())
    # Required fields present
    expected = {
        "total_return_pct", "cagr_pct", "volatility_pct", "sharpe", "sortino",
        "max_drawdown_pct", "hit_rate", "avg_win_loss_ratio", "exposure_pct",
        "turnover_pct", "gross_transaction_cost_usd", "trade_count",
    }
    assert expected.issubset(metrics["metrics"].keys())
    assert metrics["bar_count"] > 0

    # Mirror row in backtest_runs
    row = conn.execute(
        "SELECT run_id, mode, result_status FROM backtest_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert row is not None
    assert row["mode"] == "single"
    assert row["result_status"] == "succeeded"


def test_backtest_deterministic_rerun(conn: sqlite3.Connection, tmp_path: Path) -> None:
    cfg = load_config_for_backtest(FIXTURE_RULE)
    rule_text = FIXTURE_RULE.read_text(encoding="utf-8")
    config_text = _config_text()
    backtests_root = tmp_path / "backtests"

    run_dir1, run_id1 = execute_run(
        conn=conn,
        config_text=config_text,
        rule_text=rule_text,
        rule=cfg.rules[0],
        data_sources=DataSourcesConfig(),
        whitelist=cfg.whitelist,
        caps=cfg.caps,
        starting_capital_usd=Decimal("10000"),
        backtests_root=backtests_root,
    )
    metrics1 = (run_dir1 / "metrics.json").read_bytes()
    audit1 = (run_dir1 / "audit_log.jsonl").read_bytes()
    orders1 = (run_dir1 / "orders.jsonl").read_bytes()

    # Re-run with identical inputs: idempotent path returns same dir.
    run_dir2, run_id2 = execute_run(
        conn=conn,
        config_text=config_text,
        rule_text=rule_text,
        rule=cfg.rules[0],
        data_sources=DataSourcesConfig(),
        whitelist=cfg.whitelist,
        caps=cfg.caps,
        starting_capital_usd=Decimal("10000"),
        backtests_root=backtests_root,
    )
    assert run_dir1 == run_dir2
    assert run_id1 == run_id2
    assert (run_dir2 / "metrics.json").read_bytes() == metrics1
    assert (run_dir2 / "audit_log.jsonl").read_bytes() == audit1
    assert (run_dir2 / "orders.jsonl").read_bytes() == orders1


def test_backtest_run_id_changes_when_capital_changes(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Capital is part of the engine's behaviour but NOT the run_id (it
    influences metrics but not data). The run_id must change when the
    config text changes — verify by mutating a window field."""
    cfg = load_config_for_backtest(FIXTURE_RULE)
    rule_text = FIXTURE_RULE.read_text(encoding="utf-8")
    backtests_root = tmp_path / "backtests"

    _, run_id1 = execute_run(
        conn=conn,
        config_text=_config_text(),
        rule_text=rule_text,
        rule=cfg.rules[0],
        data_sources=DataSourcesConfig(),
        whitelist=cfg.whitelist,
        caps=cfg.caps,
        starting_capital_usd=Decimal("10000"),
        backtests_root=backtests_root,
    )
    # Mutate the config text (different to_utc)
    different = _config_text().replace("2025-12-31", "2025-06-30")
    _, run_id2 = execute_run(
        conn=conn,
        config_text=different,
        rule_text=rule_text,
        rule=cfg.rules[0],
        data_sources=DataSourcesConfig(),
        whitelist=cfg.whitelist,
        caps=cfg.caps,
        starting_capital_usd=Decimal("10000"),
        backtests_root=backtests_root,
    )
    assert run_id1 != run_id2
