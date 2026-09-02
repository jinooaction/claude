"""Behavioral tests for the fixed read-only deploy audit helper."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "deploy" / "deploy-audit-on-instance.sh"


def _test_helper(tmp_path: Path, db_path: Path) -> Path:
    body = HELPER.read_text(encoding="utf-8")
    body = body.replace(
        'DB_PATH="/opt/auto-invest/data/auto_invest.db"',
        f'DB_PATH="{db_path}"',
        1,
    )
    path = tmp_path / "deploy-audit"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o700)
    return path


def _audit_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE audit_log (
                seq INTEGER PRIMARY KEY,
                ts_utc TEXT NOT NULL,
                event_type TEXT NOT NULL,
                correlation_id TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        rows = (
            (1, "2026-08-31T20:59:00Z", "DEPLOY_STARTED", "a1b2c3d4", "{}"),
            (
                2,
                "2026-08-31T21:00:00Z",
                "DEPLOY_COMPLETED",
                "a1b2c3d4",
                '{"phase":"live","sha_after":"56f21c0d5833db6bfdfe1e296715cb704c264f1e"}',
            ),
            (3, "2026-08-31T21:01:00Z", "DEPLOY_STARTED", "deadbeef", "{}"),
            (
                4,
                "2026-08-31T21:02:00Z",
                "DEPLOY_COMPLETED",
                "deadbeef",
                '{"phase":"noop","sha_after":"56f21c0d5833db6bfdfe1e296715cb704c264f1e"}',
            ),
        )
        conn.executemany("INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


def test_helper_reads_latest_completed_deploy_chain(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    _audit_db(db_path)
    helper = _test_helper(tmp_path, db_path)

    before = db_path.read_bytes()
    result = subprocess.run(
        [str(helper)], capture_output=True, text=True, check=False, env={"PATH": os.environ["PATH"]}
    )

    assert result.returncode == 0, result.stderr
    assert "AUDIT_STATUS=ok" in result.stdout
    assert "AUDIT_CORRELATION_ID=deadbeef" in result.stdout
    assert "AUDIT_ROW_COUNT=2" in result.stdout
    assert "AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED" in result.stdout
    assert db_path.read_bytes() == before


def test_helper_reads_only_requested_valid_chain(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    _audit_db(db_path)
    helper = _test_helper(tmp_path, db_path)

    result = subprocess.run(
        [str(helper), "a1b2c3d4"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert "AUDIT_CORRELATION_ID=a1b2c3d4" in result.stdout
    assert "AUDIT_TERMINAL_EVENT=DEPLOY_COMPLETED" in result.stdout
    assert "deadbeef" not in result.stdout


def test_helper_reads_verified_emergency_recovery_terminal(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    _audit_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
            (
                (
                    5,
                    "2026-09-03T01:00:00Z",
                    "DEPLOY_EMERGENCY_AUTHORIZED",
                    "cafebabe",
                    '{}',
                ),
                (
                    6,
                    "2026-09-03T01:00:01Z",
                    "DEPLOY_EMERGENCY_RECOVERY_COMPLETED",
                    "cafebabe",
                    '{"recovery_basis":"subsequent-live-deploy-completed"}',
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    helper = _test_helper(tmp_path, db_path)

    result = subprocess.run(
        [str(helper)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert "AUDIT_CORRELATION_ID=cafebabe" in result.stdout
    assert "AUDIT_TERMINAL_EVENT=DEPLOY_EMERGENCY_RECOVERY_COMPLETED" in result.stdout
    assert "subsequent-live-deploy-completed" in result.stdout


def test_helper_displays_nonterminal_forward_handoff_identity(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    _audit_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
            (
                (
                    5,
                    "2026-09-03T01:00:00Z",
                    "DEPLOY_EMERGENCY_AUTHORIZED",
                    "cafebabe",
                    '{}',
                ),
                (
                    6,
                    "2026-09-03T01:00:01Z",
                    "DEPLOY_EMERGENCY_ORPHAN_RECOVERED",
                    "cafebabe",
                    '{"recovery_basis":"subsequent-live-deploy-forward-handoff",'
                    '"recovered_production_sha":"' + "a" * 40 + '"}',
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    helper = _test_helper(tmp_path, db_path)

    result = subprocess.run(
        [str(helper)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert "AUDIT_TERMINAL_EVENT=DEPLOY_EMERGENCY_ORPHAN_RECOVERED" in result.stdout
    assert "subsequent-live-deploy-forward-handoff" in result.stdout
    assert "aaaaaaaaaaaa" in result.stdout


def test_helper_rejects_shell_text_before_database_access(tmp_path: Path) -> None:
    helper = _test_helper(tmp_path, tmp_path / "missing.db")

    result = subprocess.run(
        [str(helper), "deadbeef;id"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 2
    assert "AUDIT_STATUS=invalid_correlation_id" in result.stdout
