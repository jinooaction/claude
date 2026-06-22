from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import OrderIntentPayload

runner = CliRunner()


def _db(tmp_path: Path) -> Path:
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r1",
            symbol="IEF",
            side="BUY",
            order_type="LIMIT",
            qty=1,
            limit_price_usd="94.55",
        ),
        rule_id="r1",
        symbol="IEF",
        correlation_id="cid-1",
    )
    conn.close()
    return db_path


def test_telegram_alerts_dry_run_replay_prints_message(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    state = tmp_path / "state.json"
    result = runner.invoke(
        app,
        [
            "telegram-alerts",
            "--db",
            str(db_path),
            "--state-file",
            str(state),
            "--dry-run",
            "--once",
            "--replay-existing",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "주문 의도" in result.output
    assert "symbol=IEF" in result.output
    assert "telegram-alerts processed=1" in result.output


def test_telegram_alerts_missing_secrets_is_usage_error(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    result = runner.invoke(
        app,
        ["telegram-alerts", "--db", str(db_path), "--state-file", str(tmp_path / "state.json")],
        env={"TELEGRAM_ENABLED": "false", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""},
    )
    assert result.exit_code == 2
    assert "Telegram configuration error" in result.output


def test_telegram_alerts_test_message_dry_run_needs_no_db(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["telegram-alerts", "--dry-run", "--test-message", "--db", str(tmp_path / "missing.db")],
    )
    assert result.exit_code == 0
    assert "Telegram alerts test" in result.output

