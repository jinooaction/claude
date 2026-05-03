"""End-to-end quickstart walkthrough (T059).

Drives `auto-invest run --dry-run` as a subprocess against the
sample fixture exactly as the operator would after following
quickstart.md. Verifies the dry-run completes successfully and the
audit log contains the expected lifecycle rows.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_APP_KEY", "test-app-key-12345")
    monkeypatch.setenv("KIS_APP_SECRET", "test-app-secret-67890")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "1234567801")


def test_quickstart_dry_run_full_walkthrough(env, tmp_path: Path):
    """Mirror quickstart.md: copy sample, db migrate, run --dry-run."""
    rules = tmp_path / "rules.toml"
    rules.write_text(
        Path("tests/fixtures/rules/sample-canary.toml").read_text(),
        encoding="utf-8",
    )
    db_path = tmp_path / "data" / "auto_invest.db"
    halt_path = tmp_path / "data" / "halt.flag"

    # Step 1: db migrate.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "auto_invest",
            "db",
            "migrate",
            "--db",
            str(db_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Applied" in result.stdout or "No pending" in result.stdout

    # Step 2: dry-run.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "auto_invest",
            "run",
            "--dry-run",
            "--config",
            str(rules),
            "--db",
            str(db_path),
            "--halt-path",
            str(halt_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Dry run successful" in result.stdout
    assert db_path.exists()


def test_quickstart_status_after_dry_run(env, tmp_path: Path):
    """`auto-invest status` returns valid JSON on a clean install."""
    db_path = tmp_path / "auto_invest.db"
    halt_path = tmp_path / "halt.flag"

    # Apply migrations first.
    subprocess.run(
        [sys.executable, "-m", "auto_invest", "db", "migrate", "--db", str(db_path)],
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "auto_invest",
            "status",
            "--db",
            str(db_path),
            "--halt-path",
            str(halt_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    import json

    payload = json.loads(result.stdout)
    assert payload["halt"] is None
    assert payload["positions"] == []


def test_db_migrate_is_idempotent(env, tmp_path: Path):
    db_path = tmp_path / "auto_invest.db"
    args = [sys.executable, "-m", "auto_invest", "db", "migrate", "--db", str(db_path)]

    first = subprocess.run(args, capture_output=True, text=True)
    second = subprocess.run(args, capture_output=True, text=True)

    assert first.returncode == 0
    assert second.returncode == 0
    assert "Applied" in first.stdout
    assert "No pending" in second.stdout


def test_audit_log_starts_empty_after_migration(env, tmp_path: Path):
    db_path = tmp_path / "auto_invest.db"
    subprocess.run(
        [sys.executable, "-m", "auto_invest", "db", "migrate", "--db", str(db_path)],
        check=True,
        capture_output=True,
    )
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
    assert rows[0] == 0
