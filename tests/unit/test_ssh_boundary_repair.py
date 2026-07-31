"""Tests for the server-side SSH trust-boundary repair script."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "repair-ssh-boundary.sh"
KIS_SMOKE_HELPER = REPO_ROOT / "deploy" / "kis-smoke-on-instance.sh"
OBSERVE_HELPER = REPO_ROOT / "deploy" / "observe-on-instance.sh"
REFRESH_HELPER = REPO_ROOT / "deploy" / "refresh-ssh-boundary-helpers.sh"


def _body() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _code() -> str:
    return "\n".join(
        line for line in _body().splitlines() if not line.lstrip().startswith("#")
    )


def test_repair_script_exists_and_is_executable():
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111
    assert KIS_SMOKE_HELPER.is_file()
    assert KIS_SMOKE_HELPER.stat().st_mode & 0o111
    assert OBSERVE_HELPER.is_file()
    assert OBSERVE_HELPER.stat().st_mode & 0o111
    assert REFRESH_HELPER.is_file()
    assert REFRESH_HELPER.stat().st_mode & 0o111


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
    assert re.search(r'\bkis-smoke\)', code)
    assert re.search(r'kis-smoke\\ \*\)', code)
    assert r"^[0-9a-f]{40}$" in code
    assert "/usr/local/sbin/auto-invest-kis-smoke" in code
    assert re.search(r'observe\\ halt-status\)', code)
    assert re.search(r'observe\\ paper-track-run\\ \*\)', code)
    assert re.search(r'observe\\ paper-track-verdict\\ \*\)', code)
    assert re.search(r'observe\\ ladder-forward-verdict\)', code)
    assert re.search(r'observe\\ ladder-anchored-verdict\)', code)
    assert re.search(r'observe\\ account-nav\)', code)
    assert re.search(r'observe\\ live-growth\)', code)
    assert re.search(r'observe\\ promote-readiness\)', code)
    assert not re.search(r'observe\\ promote-readiness\\ \*\)', code)
    assert r"^(trend|notrend|rmbeta|multiasset|global|globalfixed|wide)$" in code
    assert "/usr/local/sbin/auto-invest-observe" in code
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
    assert "/usr/local/sbin/auto-invest-kis-smoke" in body
    assert "/usr/local/sbin/auto-invest-observe" in body
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


def test_refresh_helpers_only_mode_reinstalls_boundary_without_key_rotation():
    body = _body()
    main_body = body[body.index("main() {") :]
    refresh_block = main_body[
        main_body.index('if [[ "${REFRESH_HELPERS_ONLY}" == "1" ]]') :
        main_body.index("validate_inputs")
    ]

    assert 'REFRESH_HELPERS_ONLY="${REFRESH_HELPERS_ONLY:-0}"' in body
    assert 'REPO="${REPO:-/opt/auto-invest}"' in body
    assert 'REPO_REF="${REPO_REF:-origin/main}"' in body
    assert "install_gateway" in refresh_block
    assert "install_sync_helper" in refresh_block
    assert "install_kis_smoke_helper" in refresh_block
    assert "install_observe_helper" in refresh_block
    assert "install_sudoers" in refresh_block
    assert "AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED" in refresh_block
    assert "install_deploy_user" not in refresh_block
    assert "install_authorized_key" not in refresh_block
    assert "retire_legacy_root_key" not in refresh_block


def test_repair_installs_helper_files_from_current_main_when_available():
    body = _body()

    assert "install_repo_file()" in body
    assert 'sudo -u "${REPO_OWNER}" git -C "${REPO}" show' in body
    assert '"${REPO_REF}:${repo_path}"' in body
    assert 'install -m 0755 -o root -g root "${tmp_file}" "${destination}"' in body
    assert '"deploy/sync-units.sh"' in body
    assert '"deploy/kis-smoke-on-instance.sh"' in body
    assert '"deploy/observe-on-instance.sh"' in body


def test_refresh_boundary_helper_is_narrow_and_main_sourced():
    assert REFRESH_HELPER.is_file()
    assert REFRESH_HELPER.stat().st_mode & 0o111
    body = REFRESH_HELPER.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("#")
    )

    assert 'REF="${REF:-origin/main}"' in body
    assert 'git -C "${REPO}" fetch origin main --quiet' in body
    assert 'git -C "${REPO}" show "${REF}:deploy/repair-ssh-boundary.sh"' in body
    assert "REFRESH_HELPERS_ONLY=1" in body
    assert "DEPLOY_PUBLIC_KEY" not in code
    assert "authorized_keys" not in code
    assert "systemctl" not in code
    assert "AUTO_INVEST_MODE=live" not in body
    assert "AUTO_INVEST_CAPITAL" not in body
    assert "rebalance" not in body.lower()
    assert "submit" not in body.lower()


def test_observe_helper_exposes_only_observation_and_paper_commands():
    body = OBSERVE_HELPER.read_text(encoding="utf-8")

    assert "paper-track-run" in body
    assert "paper-track-verdict" in body
    assert "ladder-forward-verdict" in body
    assert "ladder-anchored-verdict" in body
    assert "account-nav" in body
    assert "live-growth" in body
    assert "promote-readiness" in body
    assert "promote-check" in body
    assert "--db data/auto_invest.db" in body
    assert "--rules deploy/canary-live-rules.toml" in body
    assert "--capital 12000" in body
    assert "--mode paper" in body
    assert "--mode live" in body  # growth is read-only live evidence.
    assert "rebalance-once" in body
    assert "submit" not in body.lower()
    assert "systemctl" not in body
    assert "AUTO_INVEST_MODE=live" not in body
    assert "AUTO_INVEST_CAPITAL" not in body
    assert "eval " not in body
    assert "bash -c" not in body
