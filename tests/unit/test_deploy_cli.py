"""Tests for `auto-invest deploy` CLI surface (T029)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app


def test_health_window_below_90_rejected(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "deploy", "--health-window-s", "60",
            "--db", str(tmp_path / "x.db"),
            "--repo", str(tmp_path),
            "--supervisor", "dryrun",
        ],
    )
    assert result.exit_code == 2
    assert ">= 90" in result.stderr or ">= 90" in result.output


def test_triggered_by_invalid_rejected(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "deploy", "--triggered-by", "hacker",
            "--db", str(tmp_path / "x.db"),
            "--repo", str(tmp_path),
            "--supervisor", "dryrun",
        ],
    )
    assert result.exit_code == 2


def test_auto_tuner_without_ruleset_sha_rejected(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "deploy", "--triggered-by", "auto-tuner",
            "--db", str(tmp_path / "x.db"),
            "--repo", str(tmp_path),
            "--supervisor", "dryrun",
        ],
    )
    assert result.exit_code == 2
    assert "ruleset-sha256" in (result.stderr or "") + (result.output or "")


def test_supervisor_invalid_rejected(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "deploy", "--supervisor", "kubernetes",
            "--db", str(tmp_path / "x.db"),
            "--repo", str(tmp_path),
        ],
    )
    assert result.exit_code == 2
