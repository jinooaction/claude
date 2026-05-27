"""Spec 015 — `auto-invest fills` CLI 통합 테스트 (T012)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import db

runner = CliRunner()


def _seed_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty, state, kis_order_id)
        VALUES ('ord-1', 'r1', 'AAPL', 'BUY', 'LIMIT', 100, 'SUBMITTED', 'K1')
        """
    )
    conn.execute(
        """
        INSERT INTO fills
            (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc)
        VALUES ('ord-0', 'K0:50', 50, '120.00', '2026-05-27T10:00:00.000Z')
        """
    )
    conn.close()
    return db_path


def test_readonly_summary_lists_open_orders_and_fills(tmp_path: Path) -> None:
    db_path = _seed_db(tmp_path)
    result = runner.invoke(app, ["fills", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "열린 주문: 1건" in result.stdout
    assert "ord-1" in result.stdout and "AAPL" in result.stdout
    assert "최근 체결" in result.stdout
    assert "ord-0" in result.stdout


def test_sync_without_env_is_usage_error(tmp_path: Path) -> None:
    db_path = _seed_db(tmp_path)
    result = runner.invoke(app, ["fills", "--sync", "--db", str(db_path)])
    assert result.exit_code == 2


def test_missing_db_is_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["fills", "--db", str(tmp_path / "nope.db")])
    assert result.exit_code == 1
