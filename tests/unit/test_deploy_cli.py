"""Tests for `auto-invest deploy` CLI surface (T029)."""

from __future__ import annotations

import os
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


def test_relative_paths_anchored_to_repo(tmp_path: Path, monkeypatch):
    """Operator running `sudo -u auto-invest auto-invest deploy` from /root
    inherits cwd=/root and used to crash with PermissionError trying to mkdir
    data/ under /root. Verify that relative paths are now anchored to --repo
    so the call works from any cwd.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    # Caller's cwd is NOT the repo (mimics /root vs /opt/auto-invest).
    foreign_cwd = tmp_path / "elsewhere"
    foreign_cwd.mkdir()
    monkeypatch.chdir(foreign_cwd)

    captured: dict[str, object] = {}

    class _FakeRunner:
        def __init__(self, *, config, supervisor):
            captured["config"] = config
            self._stdout: list[str] = []
            self._stderr: list[str] = []

        def run(self):
            from auto_invest.deploy.runner import RunnerResult
            return RunnerResult(
                exit_code=0,
                correlation_id="x",
                sha_before="a",
                sha_after="b",
                phase_terminal="deploy_completed",
            )

    monkeypatch.setattr(
        "auto_invest.deploy.runner.DeployRunner", _FakeRunner
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "deploy",
            "--repo", str(repo),
            "--db", "data/auto_invest.db",          # relative on purpose
            "--config", "config/rules.toml",        # relative
            "--env-path", ".env",                   # relative
            "--supervisor", "dryrun",
        ],
    )
    assert result.exit_code == 0, (result.stdout, result.stderr)
    cfg = captured["config"]
    # repo resolved absolute
    assert cfg.repo == repo.resolve()
    # every relative input now anchored under repo, not foreign_cwd
    assert cfg.db_path == repo.resolve() / "data" / "auto_invest.db"
    assert cfg.config_path == repo.resolve() / "config" / "rules.toml"
    assert cfg.env_path == repo.resolve() / ".env"
    # pid_path explicitly anchored (was the actual crash site)
    assert cfg.pid_path == repo.resolve() / "data" / "auto_invest.deploy.pid"
    # Sanity: nothing leaked from the foreign cwd
    assert str(foreign_cwd) not in str(cfg.db_path)
    assert str(foreign_cwd) not in str(cfg.pid_path)


def test_absolute_paths_passed_through(tmp_path: Path):
    """If the caller already provides absolute paths, leave them alone."""
    repo = tmp_path / "repo"
    repo.mkdir()
    abs_db = tmp_path / "external" / "audit.db"
    abs_db.parent.mkdir()

    captured: dict[str, object] = {}

    class _FakeRunner:
        def __init__(self, *, config, supervisor):
            captured["config"] = config
            self._stdout: list[str] = []
            self._stderr: list[str] = []

        def run(self):
            from auto_invest.deploy.runner import RunnerResult
            return RunnerResult(
                exit_code=0,
                correlation_id="x",
                sha_before="a",
                sha_after="b",
                phase_terminal="deploy_completed",
            )

    import auto_invest.deploy.runner as runner_mod
    orig = runner_mod.DeployRunner
    runner_mod.DeployRunner = _FakeRunner
    try:
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "deploy",
                "--repo", str(repo),
                "--db", str(abs_db),
                "--supervisor", "dryrun",
            ],
        )
        assert result.exit_code == 0, (result.stdout, result.stderr)
        cfg = captured["config"]
        assert cfg.db_path == abs_db  # untouched
    finally:
        runner_mod.DeployRunner = orig


def test_pid_path_collision_does_not_use_cwd():
    """Regression: cwd should never influence where the deploy PID file lands.
    Even if /tmp/data/ exists writeable, the deploy CLI must not pick that."""
    # Just verify the module-level default is no longer the contract surface
    from auto_invest.deploy.guards import DEFAULT_PID_PATH
    # The default is still a relative anchor (for unit tests + dev mode),
    # but the CLI replaces it with an absolute repo-anchored path.
    # The CLI test above proves the substitution actually happens.
    assert not DEFAULT_PID_PATH.is_absolute()
    # And the directory portion is still 'data' (sanity)
    assert DEFAULT_PID_PATH.parent == Path("data")
    _ = os.environ  # silence linter; this test is intentionally lightweight
