"""스펙 035 후속 — forward-verdict-anchored CLI 페일세이프 배선 테스트.

happy-path(깊은 인제스트 데이터셋 + 라이브 forward 스냅샷)는 인스턴스에서 돌고, 여기서는
명령이 올바르게 등록되고 데이터 부족 시 *안전하게* 종료하는지(읽기 전용·돈 0) 확인한다.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import db

runner = CliRunner()


def test_anchored_missing_db_exits_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "forward-verdict-anchored",
            "--portfolio",
            "deploy/global-trend-portfolio.toml",
            "--db",
            str(tmp_path / "nope.db"),
            "--trailing-years",
            "5",
        ],
    )
    assert result.exit_code == 1
    assert "DB 파일을 찾을 수 없습니다" in (result.stdout + str(result.stderr))


def test_anchored_no_dataset_exits_cleanly(tmp_path: Path) -> None:
    # DB 는 있지만 인제스트 데이터셋이 없으면 안전 종료(64) — OOS 앵커 불가.
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.close()
    result = runner.invoke(
        app,
        [
            "forward-verdict-anchored",
            "--portfolio",
            "deploy/global-trend-portfolio.toml",
            "--db",
            str(db_path),
            "--history-root",
            str(tmp_path / "empty-history"),
            "--trailing-years",
            "5",
        ],
    )
    assert result.exit_code == 64
    assert "ingested datasets" in (result.stdout + str(result.stderr))


def test_anchored_command_is_registered() -> None:
    result = runner.invoke(app, ["forward-verdict-anchored", "--help"])
    assert result.exit_code == 0
    assert "백테스트 앵커드 엣지 판정" in result.stdout
