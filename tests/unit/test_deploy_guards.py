"""Tests for deploy preconditions (T011)."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from auto_invest.deploy.guards import (
    LockContention,
    acquire_lock,
    dirty_tree_check,
    idempotency_check,
    market_hours_guard,
    secrets_present,
)

# ---------------- market_hours_guard ----------------


def test_market_open_during_us_session():
    # 2024-06-03 (Monday) at 15:00 UTC — NYSE open 13:30Z-20:00Z
    now = datetime(2024, 6, 3, 15, 0, 0, tzinfo=UTC)
    decision = market_hours_guard(now=now)
    assert decision.allowed is False
    assert "open" in decision.refusal_reason()


def test_market_closed_weekend():
    # 2024-06-01 (Saturday) — always closed
    now = datetime(2024, 6, 1, 15, 0, 0, tzinfo=UTC)
    decision = market_hours_guard(now=now)
    assert decision.allowed is True


def test_market_closed_pre_open_utc():
    # 2024-06-03 (Monday) at 06:00 UTC — well before NYSE opens
    now = datetime(2024, 6, 3, 6, 0, 0, tzinfo=UTC)
    decision = market_hours_guard(now=now)
    assert decision.allowed is True


# ---------------- dirty_tree_check ----------------


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t.t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    # Disable GPG signing in this test repo only — the harness signs by
    # default but our throwaway test repos must not require a signing
    # server.
    subprocess.run(
        ["git", "-C", str(path), "config", "commit.gpgsign", "false"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "tag.gpgsign", "false"], check=True,
    )


def test_clean_tree(tmp_path):
    _init_git_repo(tmp_path)
    decision = dirty_tree_check(tmp_path)
    assert decision.is_dirty is False
    assert decision.allowed is True


def test_dirty_tree(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "f.txt").write_text("hi")
    decision = dirty_tree_check(tmp_path)
    assert decision.is_dirty is True
    assert decision.allowed is False
    assert "f.txt" in decision.porcelain


# ---------------- secrets_present ----------------


def test_secrets_via_env_vars(monkeypatch, tmp_path):
    for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO"):
        monkeypatch.setenv(key, "x")
    decision = secrets_present(env_path=tmp_path / "missing.env")
    assert decision.allowed is True


def test_secrets_via_env_file(monkeypatch, tmp_path):
    for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        'KIS_APP_KEY=keyval\n'
        'KIS_APP_SECRET="secretval"\n'
        "KIS_ACCOUNT_NO=12345\n"
    )
    decision = secrets_present(env_path=env)
    assert decision.allowed is True


def test_secrets_missing(monkeypatch, tmp_path):
    for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO"):
        monkeypatch.delenv(key, raising=False)
    decision = secrets_present(env_path=tmp_path / "missing.env")
    assert decision.allowed is False
    assert set(decision.missing) == {
        "KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO",
    }


# ---------------- acquire_lock ----------------


def test_lock_acquire_fresh(tmp_path):
    pid_path = tmp_path / "deploy.pid"
    handle = acquire_lock(pid_path)
    try:
        assert pid_path.exists()
        assert int(pid_path.read_text().strip()) == os.getpid()
    finally:
        handle.release()
    assert not pid_path.exists()


def test_lock_stale_pid_overwritten(tmp_path, monkeypatch):
    pid_path = tmp_path / "deploy.pid"
    pid_path.write_text("999999\n")  # pid that does not exist

    def fake_alive(pid):  # noqa: ARG001
        return (False, "")

    monkeypatch.setattr("auto_invest.deploy.guards._process_alive", fake_alive)
    handle = acquire_lock(pid_path)
    try:
        assert int(pid_path.read_text().strip()) == os.getpid()
    finally:
        handle.release()


def test_lock_contention_when_pid_alive_and_auto_invest(tmp_path, monkeypatch):
    pid_path = tmp_path / "deploy.pid"
    pid_path.write_text("12345\n")
    monkeypatch.setattr(
        "auto_invest.deploy.guards._process_alive",
        lambda pid: (True, "uv run auto-invest deploy"),
    )
    with pytest.raises(LockContention) as excinfo:
        acquire_lock(pid_path)
    assert excinfo.value.pid == 12345


def test_lock_pid_alive_but_not_auto_invest_is_stale(tmp_path, monkeypatch):
    pid_path = tmp_path / "deploy.pid"
    pid_path.write_text("12345\n")
    monkeypatch.setattr(
        "auto_invest.deploy.guards._process_alive",
        lambda pid: (True, "vim"),
    )
    handle = acquire_lock(pid_path)
    try:
        assert int(pid_path.read_text().strip()) == os.getpid()
    finally:
        handle.release()


# ---------------- idempotency_check ----------------


def test_idempotency_noop_when_head_equals_origin(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "a.txt").write_text("a")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "branch", "-m", "main"], check=True,
    )
    # Add a local-only remote pointing at itself; simulate by manual fetch refs:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(bare)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True,
    )
    decision = idempotency_check(repo, "main")
    assert decision.is_noop is True


def test_idempotency_changes_pending(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "a.txt").write_text("a")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "-m", "main"], check=True)
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(bare)], check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True,
    )
    # Now make a SECOND commit and push it from a sibling clone — repo's HEAD
    # will lag origin's main.
    sibling = tmp_path / "sibling"
    subprocess.run(
        ["git", "clone", "-q", "--branch", "main", str(bare), str(sibling)], check=True,
    )
    subprocess.run(
        ["git", "-C", str(sibling), "config", "user.email", "t@t.t"], check=True,
    )
    subprocess.run(["git", "-C", str(sibling), "config", "user.name", "t"], check=True)
    subprocess.run(
        ["git", "-C", str(sibling), "config", "commit.gpgsign", "false"], check=True,
    )
    (sibling / "b.txt").write_text("b")
    subprocess.run(["git", "-C", str(sibling), "add", "b.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(sibling), "commit", "-q", "-m", "b"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(sibling), "push", "-q", "origin", "main"], check=True,
    )
    decision = idempotency_check(repo, "main")
    assert decision.is_noop is False
    assert decision.sha_local != decision.sha_remote
