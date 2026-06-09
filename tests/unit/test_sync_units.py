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
    """The WORKER (auto-invest.service) may be enabled, but NEVER restarted/started
    here — that is the deploy state machine's job, with its own market-hours +
    health gates."""
    code = _code()
    # The worker service must never be restarted/started here.
    assert not re.search(r"restart\s+auto-invest", code), "must not restart the worker"
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


# ───────────────────────── worker-control authorization (sudo) ─────────


SUDOERS = REPO_ROOT / "deploy" / "auto-invest-deploy.sudoers"


def test_sudoers_exists_and_is_narrowly_scoped():
    """The sudoers drop-in must authorise ONLY the worker unit's systemctl verbs
    for the auto-invest user — never a broad NOPASSWD grant."""
    assert SUDOERS.is_file(), "deploy/auto-invest-deploy.sudoers must exist"
    body = SUDOERS.read_text(encoding="utf-8")
    assert "auto-invest ALL=(root) NOPASSWD:" in body
    assert "/usr/bin/systemctl stop auto-invest.service" in body
    assert "/usr/bin/systemctl start auto-invest.service" in body
    # No blanket grant (must not authorise ALL commands).
    assert "NOPASSWD: ALL" not in body
    assert "NOPASSWD:ALL" not in body


def test_sync_units_installs_sudoers_with_visudo_validation():
    """sync-units.sh must (re)install the sudoers drop-in, validating with visudo
    FIRST (a malformed /etc/sudoers.d file breaks all sudo on the host)."""
    code = _code()
    assert "auto-invest-deploy.sudoers" in code
    assert "/etc/sudoers.d/auto-invest-deploy" in code
    assert "visudo -cf" in code        # validate before install
    assert "install -m 0440" in code   # sudoers must be 0440


def test_deploy_service_has_no_new_privileges_disabled():
    """The deploy oneshot must NOT set NoNewPrivileges=true — it blocks sudo
    (setuid), which the worker-control path now relies on."""
    unit = (REPO_ROOT / "deploy" / "auto-invest-deploy.service").read_text(
        encoding="utf-8"
    )
    # strip comment lines, then assert the directive is absent
    active = "\n".join(
        ln for ln in unit.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "NoNewPrivileges=true" not in active


def test_deploy_workflow_syncs_units_before_deploy():
    """The unit/sudoers sync step MUST run before the deploy step: the deploy state
    machine's stop_worker needs the sudoers drop-in already installed to succeed."""
    wf = (REPO_ROOT / ".github" / "workflows" / "deploy-on-merge.yml").read_text(
        encoding="utf-8"
    )
    units_idx = wf.index("id: units")
    deploy_idx = wf.index("id: deploy")
    assert units_idx < deploy_idx, "units/sudoers sync must precede the deploy step"
