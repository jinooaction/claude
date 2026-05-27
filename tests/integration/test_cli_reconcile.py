"""스펙 001 T050 — `auto-invest reconcile` CLI 사용성 테스트.

브로커 조회 경로(토큰+잔고)는 `test_reconciliation.py`(run_reconciliation) 와 워커
틱 자동 트리거 테스트가 검증하므로, 여기서는 명령의 사용 오류 분기만 확인한다.
"""

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
    conn.close()
    return db_path


def _env(tmp_path: Path) -> Path:
    env = tmp_path / ".env"
    env.write_text(
        "KIS_APP_KEY=k\nKIS_APP_SECRET=s\nKIS_ACCOUNT_NO=1234567801\n"
        "AUTO_INVEST_CAPITAL=100\n"
    )
    return env


def test_reconcile_without_env_is_usage_error(tmp_path: Path) -> None:
    db_path = _seed_db(tmp_path)
    result = runner.invoke(app, ["reconcile", "--db", str(db_path)])
    assert result.exit_code == 2


def test_reconcile_missing_db_is_usage_error(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = runner.invoke(
        app,
        ["reconcile", "--db", str(tmp_path / "nope.db"), "--env", str(env)],
    )
    assert result.exit_code == 2
