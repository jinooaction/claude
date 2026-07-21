"""Tests for the server-side SSH trust-boundary repair script."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "repair-ssh-boundary.sh"


def _body() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _code() -> str:
    return "\n".join(
        line for line in _body().splitlines() if not line.lstrip().startswith("#")
    )


def test_repair_script_exists_and_is_executable():
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111


def test_requires_root_and_public_key_not_private_key():
    body = _body()

    assert 'id -u' in body
    assert 'DEPLOY_PUBLIC_KEY is required' in body
    assert 'PRIVATE KEY' in body
    assert 'not an OpenSSH public key' in body


def test_installs_non_root_forced_command_deploy_user():
    body = _body()

    assert 'DEPLOY_USER="${DEPLOY_USER:-gh-deploy}"' in body
    assert "useradd --system" in body
    assert "authorized_keys" in body
    assert 'command="%s"' in body
    assert "auto-invest-deploy-gateway" in body
    assert "restrict" in body
    assert "no-pty" in body
    assert "no-agent-forwarding" in body
    assert "no-port-forwarding" in body


def test_gateway_allows_only_fixed_commands_without_eval():
    code = _code()

    assert 'cmd="${SSH_ORIGINAL_COMMAND:-status}"' in code
    assert re.search(r'\bstatus\)', code)
    assert re.search(r'\bsync-units\)', code)
    assert re.search(r'\bstart-deploy\)', code)
    assert re.search(r'\bdeploy-journal\)', code)
    assert "refused command" in code
    assert "eval " not in code
    assert "bash -c" not in code


def test_sudoers_is_narrow_and_visudo_validated():
    body = _body()

    assert "visudo -cf" in body
    assert "/etc/sudoers.d/auto-invest-gh-deploy" in body
    assert "NOPASSWD:" in body
    assert "NOPASSWD: ALL" not in body
    assert "/usr/local/sbin/auto-invest-sync-units" in body
    assert "/usr/bin/systemctl start auto-invest-deploy.service" in body
    assert "/usr/bin/journalctl -u auto-invest-deploy.service -n 120 --no-pager" in body


def test_root_key_retirement_is_targeted_not_blanket_delete():
    body = _body()

    assert "github-actions@auto-invest" in body
    assert "/root/.ssh/auto_invest_gh" in body
    assert ".pre-auto-invest-boundary-" in body
    assert "rm -f ${ROOT_AUTHORIZED_KEYS}" not in body
    assert "> ${ROOT_AUTHORIZED_KEYS}" not in body
    assert "retired-auto-invest-root-key" in body


def test_script_does_not_change_live_money_or_worker_state():
    body = _body()

    assert "AUTO_INVEST_MODE=live" not in body
    assert "AUTO_INVEST_CAPITAL" not in body
    assert "systemctl restart auto-invest.service" not in body
    assert "systemctl start auto-invest.service" not in body
