"""Spec 013 — `auto-invest health` CLI 통합 테스트.

검증:
  - 깨끗한 시스템 → 종합 OK, 종료 코드 0 (SC-H01).
  - 정합성 MISMATCH → 종합 CRITICAL, 종료 코드 1 (SC-H02).
  - halt 설정 → DEGRADED, 종료 코드 1.
  - DB 없음 → CRITICAL, 종료 코드 1 (빈 DB 생성 안 함, FR-H03).
  - json 출력에 schema_version·overall·checks 포함.
  - read-only — 실행 전후 audit_log row 수 불변 (SC-H03).
  - 잘못된 --format → 종료 코드 2.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import db
from auto_invest.worker.halt import set_halt

runner = CliRunner()


def _fresh_db(tmp_path: Path) -> Path:
    """Healthy-looking system: live worker PID + recent reconciliation OK + activity."""
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.execute(
        "INSERT INTO reconciliation_runs (started_at_utc, finished_at_utc, result) "
        "VALUES (strftime('%Y-%m-%dT%H:%M:%S.000Z','now'), "
        "strftime('%Y-%m-%dT%H:%M:%S.000Z','now'), 'OK')"
    )
    # Benign recent activity (not an ERROR) so activity is fresh and
    # recent_errors stays clean.
    conn.execute(
        "INSERT INTO audit_log (ts_utc, event_type, payload_json) "
        "VALUES (strftime('%Y-%m-%dT%H:%M:%S.000Z','now'), 'WORKER_STARTED', '{}')"
    )
    conn.commit()
    conn.close()
    # Live worker PID file.
    (db_path.parent / "auto_invest.pid").write_text(str(os.getpid()))
    return db_path


def _row_count(db_path: Path) -> int:
    conn = db.get_connection(db_path)
    n = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    conn.close()
    return n


def test_healthy_system_ok_exit_0(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    before = _row_count(db_path)
    result = runner.invoke(
        app,
        ["health", "--db", str(db_path), "--halt-path", str(tmp_path / "halt.flag"),
         "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["overall"] == "OK"
    assert payload["schema_version"] == "1.0"
    assert any(c["name"] == "worker_liveness" for c in payload["checks"])
    # read-only
    assert _row_count(db_path) == before


def test_mismatch_critical_exit_1(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    conn = db.get_connection(db_path)
    conn.execute(
        "INSERT INTO reconciliation_runs (started_at_utc, finished_at_utc, result) "
        "VALUES (strftime('%Y-%m-%dT%H:%M:%S.000Z','now'), "
        "strftime('%Y-%m-%dT%H:%M:%S.000Z','now'), 'MISMATCH')"
    )
    conn.commit()
    conn.close()
    result = runner.invoke(
        app,
        ["health", "--db", str(db_path), "--halt-path", str(tmp_path / "halt.flag"),
         "--format", "json"],
    )
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["overall"] == "CRITICAL"


def test_halt_degraded_exit_1(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    halt_path = tmp_path / "halt.flag"
    set_halt(halt_path, "operator paused for review")
    result = runner.invoke(
        app,
        ["health", "--db", str(db_path), "--halt-path", str(halt_path), "--format", "json"],
    )
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    halt_check = next(c for c in payload["checks"] if c["name"] == "halt")
    assert halt_check["status"] == "DEGRADED"


def test_missing_db_critical_exit_1_no_db_created(tmp_path: Path):
    missing = tmp_path / "nope.db"
    result = runner.invoke(app, ["health", "--db", str(missing), "--format", "json"])
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["overall"] == "CRITICAL"
    assert payload["checks"][0]["name"] == "database"
    # FR-H03: must not create an empty DB file.
    assert not missing.exists()


def test_text_output_has_verdict(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    result = runner.invoke(
        app, ["health", "--db", str(db_path), "--halt-path", str(tmp_path / "halt.flag")]
    )
    assert result.exit_code == 0, result.stdout
    assert "종합 판정: OK" in result.stdout


def test_bad_format_exit_2(tmp_path: Path):
    db_path = _fresh_db(tmp_path)
    result = runner.invoke(app, ["health", "--db", str(db_path), "--format", "xml"])
    assert result.exit_code == 2
