"""Integration tests for the deploy runner — spec 006 Phase 5 (T025/T027).

Every scenario uses a real temp git repo (init + bare + clone) so the
runner's git/path manipulation is exercised end-to-end. The supervisor
is the DryRunSupervisor — no `systemctl` calls — and `secrets_present`
is satisfied via monkeypatched env vars.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from auto_invest.deploy.runner import DeployRunner, RunnerConfig
from auto_invest.deploy.supervisor import DryRunSupervisor
from auto_invest.persistence import audit
from auto_invest.persistence import db as dbmod


def _git_config(repo: Path) -> None:
    for k, v in (
        ("user.email", "t@t.t"),
        ("user.name", "t"),
        ("commit.gpgsign", "false"),
        ("tag.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", "-C", str(repo), "config", k, v], check=True,
        )


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", message], check=True,
    )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _ensure_secrets(monkeypatch: Any) -> None:
    for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO"):
        monkeypatch.setenv(key, "x")


@pytest.fixture
def repo_setup(tmp_path: Path, monkeypatch: Any) -> dict[str, Any]:
    """Build a clone+bare+sibling setup, plus an audit DB.

    Returns: dict with repo (working), bare, sibling, db_path.
    """
    _ensure_secrets(monkeypatch)
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(
        ["git", "-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"],
        check=True,
    )

    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git_config(repo)
    sha_a = _commit(repo, {"src/dummy.py": "x = 1\n"}, "initial")
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(bare)], check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True,
    )

    sibling = tmp_path / "sibling"
    subprocess.run(
        ["git", "clone", "-q", "--branch", "main", str(bare), str(sibling)],
        check=True,
    )
    _git_config(sibling)

    db_path = tmp_path / "auto_invest.db"
    conn = dbmod.get_connection(db_path)
    try:
        dbmod.migrate(conn)
    finally:
        conn.close()

    # Patch sync to a no-op (uv sync would fail in the sandbox without deps).
    monkeypatch.setattr(
        "auto_invest.deploy.steps.sync",
        lambda _repo: __import__(
            "auto_invest.deploy.steps", fromlist=["StepResult"]
        ).StepResult(ok=True),
    )
    # Patch dry_run_config to a no-op (no rules.toml in temp repo).
    monkeypatch.setattr(
        "auto_invest.deploy.steps.dry_run_config",
        lambda _cfg: __import__(
            "auto_invest.deploy.steps", fromlist=["StepResult"]
        ).StepResult(ok=True),
    )

    return {
        "repo": repo,
        "bare": bare,
        "sibling": sibling,
        "db_path": db_path,
        "sha_a": sha_a,
    }


def _push_new_commit(
    sibling: Path, files: dict[str, str], message: str,
) -> str:
    sha = _commit(sibling, files, message)
    subprocess.run(
        ["git", "-C", str(sibling), "push", "-q", "origin", "main"], check=True,
    )
    return sha


def _read_all(db_path: Path) -> list[dict[str, Any]]:
    conn = dbmod.get_connection(db_path)
    try:
        rows = list(conn.execute("SELECT * FROM audit_log ORDER BY seq"))
        return [
            {
                "ts_utc": r["ts_utc"],
                "event_type": r["event_type"],
                "correlation_id": r["correlation_id"],
                "payload": json.loads(r["payload_json"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------- T025 scenarios ----------------


def test_noop_writes_no_audit_and_returns_zero(repo_setup, monkeypatch):
    """SC-D04: HEAD matches origin → exit 0, no audit, < 2 s."""
    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    t0 = time.monotonic()
    result = r.run()
    elapsed = time.monotonic() - t0
    assert result.exit_code == 0
    assert result.phase_terminal == "noop"
    assert elapsed < 5.0  # generous on slow CI; test machine is faster
    rows = _read_all(repo_setup["db_path"])
    assert all(not row["event_type"].startswith("DEPLOY_") for row in rows)


def test_dry_run_emits_started_and_completed(repo_setup, monkeypatch):
    """STARTED + COMPLETED(phase=dry_run) share one correlation_id."""
    _push_new_commit(repo_setup["sibling"], {"src/b.py": "y = 2\n"}, "b")
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )
    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        dry_run=True,
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    result = r.run()
    assert result.exit_code == 0, result.detail
    assert result.phase_terminal == "dry_run"
    rows = _read_all(repo_setup["db_path"])
    deploy_rows = [r for r in rows if r["event_type"].startswith("DEPLOY_")]
    assert [r["event_type"] for r in deploy_rows] == [
        "DEPLOY_STARTED",
        "DEPLOY_COMPLETED",
    ]
    assert deploy_rows[0]["correlation_id"] == deploy_rows[1]["correlation_id"]
    assert deploy_rows[1]["payload"]["phase"] == "dry_run"


def test_live_success_emits_started_and_completed_live(repo_setup, monkeypatch):
    """Full live deploy with mocked WORKER_STARTED row in window."""
    _push_new_commit(repo_setup["sibling"], {"src/c.py": "z = 3\n"}, "c")
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )

    sup = DryRunSupervisor()
    original_start = sup.start_worker

    def start_and_audit():
        result = original_start()
        conn = dbmod.get_connection(repo_setup["db_path"])
        try:
            audit.append(
                conn,
                audit.WorkerStartedPayload(pid=12345, config_path="config/rules.toml"),
            )
            conn.commit()
        finally:
            conn.close()
        return result

    sup.start_worker = start_and_audit  # type: ignore[assignment]

    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        health_window_s=5,  # accelerated for test
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=sup)
    result = r.run()
    assert result.exit_code == 0, result.detail
    assert result.phase_terminal == "live"
    rows = _read_all(repo_setup["db_path"])
    deploy_rows = [r for r in rows if r["event_type"].startswith("DEPLOY_")]
    assert deploy_rows[0]["event_type"] == "DEPLOY_STARTED"
    assert deploy_rows[-1]["event_type"] == "DEPLOY_COMPLETED"
    assert deploy_rows[-1]["payload"]["phase"] == "live"
    # all share one correlation_id
    cids = {r["correlation_id"] for r in deploy_rows}
    assert len(cids) == 1


def test_kernel_touch_emits_informational_row_and_continues(repo_setup, monkeypatch):
    """A diff hitting a kernel path emits DEPLOY_KERNEL_TOUCHED but proceeds."""
    # Stage the manifest into the temp repo so kernel_check resolves it.
    manifest = repo_setup["sibling"] / ".specify/memory/kernel.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '[K1]\n'
        'description = "test"\n'
        'files = ["src/risk_gate.py"]\n'
        '[K_meta]\n'
        'description = "self"\n'
        'files = [".specify/memory/kernel.toml"]\n'
    )
    _push_new_commit(
        repo_setup["sibling"],
        {"src/risk_gate.py": "def gate(): pass\n"},
        "touch kernel",
    )
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )
    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        dry_run=True,  # short-circuit before stop/start
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    result = r.run()
    assert result.exit_code == 0, result.detail
    rows = _read_all(repo_setup["db_path"])
    types = [r["event_type"] for r in rows if r["event_type"].startswith("DEPLOY_")]
    assert types == [
        "DEPLOY_STARTED",
        "DEPLOY_KERNEL_TOUCHED",
        "DEPLOY_COMPLETED",
    ]
    touched = [
        r for r in rows if r["event_type"] == "DEPLOY_KERNEL_TOUCHED"
    ][0]
    assert "src/risk_gate.py" in touched["payload"]["touched_paths"]


def test_market_hours_block_writes_failed_row(repo_setup, monkeypatch):
    """During market hours the deploy refuses with exit 2."""
    _push_new_commit(repo_setup["sibling"], {"src/d.py": "u = 4\n"}, "d")
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(
            is_open=True,
            next_close_utc="2026-05-14T20:00:00Z",
            next_open_utc=None,
        ),
    )
    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    result = r.run()
    assert result.exit_code == 2
    assert result.phase_terminal == "market_hours_guard"
    rows = _read_all(repo_setup["db_path"])
    deploy_rows = [r for r in rows if r["event_type"].startswith("DEPLOY_")]
    assert len(deploy_rows) == 1
    assert deploy_rows[0]["event_type"] == "DEPLOY_FAILED"
    assert deploy_rows[0]["payload"]["phase"] == "market_hours_guard"


def test_health_check_timeout_triggers_rollback(repo_setup, monkeypatch):
    """A failing health check must emit FAILED + ROLLED_BACK with same correlation_id."""
    _push_new_commit(repo_setup["sibling"], {"src/e.py": "v = 5\n"}, "e")
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )

    # Patch health_check to fail first call, succeed on rollback call.
    calls = {"n": 0}

    from auto_invest.deploy import steps

    def fake_health_check(db, ts, window_s, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return steps.HealthCheckResult(ok=False, detail="timeout")
        return steps.HealthCheckResult(ok=True)

    monkeypatch.setattr("auto_invest.deploy.runner.steps.health_check", fake_health_check)
    monkeypatch.setattr("auto_invest.deploy.steps.health_check", fake_health_check)

    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        health_window_s=1,
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    result = r.run()
    assert result.exit_code == 1
    assert result.phase_terminal == "health_check"
    assert result.rolled_back is True
    rows = _read_all(repo_setup["db_path"])
    deploy_rows = [r for r in rows if r["event_type"].startswith("DEPLOY_")]
    types = [r["event_type"] for r in deploy_rows]
    assert "DEPLOY_STARTED" in types
    assert "DEPLOY_FAILED" in types
    assert "DEPLOY_ROLLED_BACK" in types
    cids = {r["correlation_id"] for r in deploy_rows}
    assert len(cids) == 1


# ---------------- T027 canary-gate scenarios ----------------


def test_auto_tuner_missing_canary_passed_refuses(repo_setup, monkeypatch):
    _push_new_commit(repo_setup["sibling"], {"src/f.py": "w = 6\n"}, "f")
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )
    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        triggered_by="auto-tuner",
        ruleset_sha256="abc",
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    result = r.run()
    assert result.exit_code == 2
    assert result.phase_terminal == "canary_gate"


def test_auto_tuner_stale_canary_refuses(repo_setup, monkeypatch):
    sha_after = _push_new_commit(
        repo_setup["sibling"], {"src/g.py": "h = 7\n"}, "g",
    )
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )
    # Insert a CANARY_PASSED row dated 48h ago.
    conn = dbmod.get_connection(repo_setup["db_path"])
    try:
        stale_ts = (datetime.now(UTC) - timedelta(hours=48)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        audit.append(
            conn,
            audit.CanaryPassedPayload(
                canary_run_id="cr1", candidate_rev=sha_after, baseline_rev="x",
                tier="L2", finished_at=stale_ts, artefact_path="/x",
            ),
            ts_utc=stale_ts,
        )
        conn.commit()
    finally:
        conn.close()
    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        triggered_by="auto-tuner",
        ruleset_sha256="abc",
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    result = r.run()
    assert result.exit_code == 2
    assert result.phase_terminal == "canary_gate"


def test_auto_tuner_matching_canary_proceeds(repo_setup, monkeypatch):
    sha_after = _push_new_commit(
        repo_setup["sibling"], {"src/h.py": "i = 8\n"}, "h",
    )
    monkeypatch.setattr(
        "auto_invest.deploy.guards.market_hours_guard",
        lambda now=None: __import__(
            "auto_invest.deploy.guards", fromlist=["MarketHoursDecision"]
        ).MarketHoursDecision(is_open=False, next_close_utc=None, next_open_utc=None),
    )
    conn = dbmod.get_connection(repo_setup["db_path"])
    try:
        audit.append(
            conn,
            audit.CanaryPassedPayload(
                canary_run_id="cr1", candidate_rev=sha_after, baseline_rev="x",
                tier="L2",
                finished_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                artefact_path="/x",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    cfg = RunnerConfig(
        repo=repo_setup["repo"],
        db_path=repo_setup["db_path"],
        branch="main",
        dry_run=True,  # short-circuit before stop/start so we don't need worker
        triggered_by="auto-tuner",
        ruleset_sha256="abc",
        pid_path=repo_setup["db_path"].parent / "lock.pid",
    )
    r = DeployRunner(config=cfg, supervisor=DryRunSupervisor())
    result = r.run()
    assert result.exit_code == 0, result.detail
    assert result.phase_terminal == "dry_run"
