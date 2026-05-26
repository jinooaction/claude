"""Tests for deploy/sync-units.sh — the server-side systemd unit installer.

deploy-on-merge.yml pipes this script to the host's `sudo bash`. It must
install/refresh the deploy unit files and enable the timers WITHOUT ever
restarting the worker, and WITHOUT dirtying the git working tree (so it cannot
collide with the spec 006 deploy state machine's clean-tree check). These
assertions lock those safety properties in.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "sync-units.sh"

EXPECTED_UNITS = (
    "auto-invest.service",
    "auto-invest-deploy.service",
    "auto-invest-deploy.timer",
    "auto-invest-tune.service",
    "auto-invest-tune.timer",
)


def _body() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _code() -> str:
    """Script body with comment lines stripped (so prose mentioning a command
    does not count as using it)."""
    lines = [
        ln for ln in _body().splitlines() if not ln.lstrip().startswith("#")
    ]
    return "\n".join(lines)


def test_script_exists_and_executable():
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111, "sync-units.sh must be executable"


def test_installs_every_deploy_unit():
    body = _body()
    for unit in EXPECTED_UNITS:
        assert unit in body, f"sync-units.sh must handle {unit}"
    assert "/etc/systemd/system/" in body
    assert "install -m 0644" in body


def test_enables_both_timers_now():
    body = _body()
    assert "enable --now auto-invest-deploy.timer" in body
    assert "enable --now auto-invest-tune.timer" in body


def test_never_restarts_or_starts_the_worker():
    """The worker may be enabled, but NEVER restarted/started here — that is
    the deploy state machine's job, with its own market-hours + health gates."""
    code = _code()
    assert "restart" not in code, "sync-units.sh must not restart anything"
    # No `systemctl start`/`--now` applied to the worker service.
    assert not re.search(r"start\s+auto-invest\.service", code)
    assert not re.search(r"enable\s+--now\s+auto-invest\.service", code)


def test_does_not_dirty_the_working_tree():
    """Must read unit content via `git show <ref>:path`, never checkout/pull/reset
    (those modify the tree and would trip the deploy machine's dirty-tree guard)."""
    code = _code()
    assert "git" in code and "show" in code
    assert "origin/main" in code
    assert "git checkout" not in code
    assert "git pull" not in code
    assert "git reset" not in code


def test_runs_git_as_repo_owner_not_root():
    """Avoids git 'dubious ownership' by running git as the auto-invest user."""
    body = _body()
    assert "sudo -u auto-invest git" in body


def test_workflow_pipes_script_and_checks_out():
    wf = (REPO_ROOT / ".github" / "workflows" / "deploy-on-merge.yml").read_text(
        encoding="utf-8"
    )
    assert "actions/checkout" in wf, "runner must check out to pipe the script"
    assert "'sudo bash -s' < deploy/sync-units.sh" in wf
    # Unit-sync result is surfaced but independent of the code-deploy exit.
    assert "units_exit" in wf
