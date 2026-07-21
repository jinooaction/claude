"""Regression tests for repository-controlled security hardening."""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
_REDACTOR_SPEC = importlib.util.spec_from_file_location(
    "redact_public_sidecar",
    REPO_ROOT / "scripts" / "redact_public_sidecar.py",
)
assert _REDACTOR_SPEC is not None and _REDACTOR_SPEC.loader is not None
_REDACTOR = importlib.util.module_from_spec(_REDACTOR_SPEC)
_REDACTOR_SPEC.loader.exec_module(_REDACTOR)


def _workflow_texts() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml")}


def test_third_party_actions_are_pinned_to_full_commit_sha():
    violations: list[str] = []
    for path, text in _workflow_texts().items():
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("uses: "):
                continue
            target = stripped.removeprefix("uses: ").strip()
            if target.startswith("./") or "@" not in target:
                continue
            ref = target.rsplit("@", 1)[1]
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                violations.append(f"{path.name}:{line_no}:{target}")
    assert violations == []


def test_ssh_workflows_use_fixed_known_hosts_not_accept_new():
    violations: list[str] = []
    for path, text in _workflow_texts().items():
        if "StrictHostKeyChecking=accept-new" in text:
            violations.append(f"{path.name}: still accepts new host keys")
        if "StrictHostKeyChecking=yes" in text:
            if "UserKnownHostsFile=~/.ssh/known_hosts" not in text:
                violations.append(f"{path.name}: strict host key without known_hosts file")
            if "VULTR_SSH_KNOWN_HOSTS" not in text:
                violations.append(f"{path.name}: strict host key without known-host secret")
    assert violations == []


def test_ssh_workflows_refuse_root_user():
    violations = [
        path.name
        for path, text in _workflow_texts().items()
        if "VULTR_SSH_USER" in text and "VULTR_SSH_USER=root is refused" not in text
    ]
    assert violations == []


def test_go_live_script_fails_closed_and_restores_full_env():
    script = (REPO_ROOT / "deploy" / "go-live-canary.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    assert "EXPECTED_SHA" in script
    assert 'market_state" != "CLOSED"' in script
    assert "GO_LIVE_RESULT=market_state_unknown" in script
    assert 'tmp_env="$(mktemp "$(dirname "$ENV_FILE")/.env.golive.XXXXXX")"' in script
    assert 'mv -f "$tmp_env" "$ENV_FILE"' in script
    assert 'cp -a "${ENV_FILE}.pre-golive.bak" "$ENV_FILE"' in script


def test_go_live_workflow_passes_expected_sha_to_server():
    workflow = (WORKFLOWS / "go-live-canary.yml").read_text(encoding="utf-8")
    assert "sudo env EXPECTED_SHA='${GITHUB_SHA}' bash -s" in workflow


def test_env_files_are_parsed_as_data_not_sourced():
    searchable = [
        *WORKFLOWS.glob("*.yml"),
        *(REPO_ROOT / "scripts").glob("*.sh"),
        *(REPO_ROOT / "deploy").glob("*.sh"),
    ]
    violations: list[str] = []
    for path in searchable:
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?m)^\s*(?:source|\.)\s+.*\.env\b", text):
            violations.append(path.relative_to(REPO_ROOT).as_posix())
    assert violations == []


def test_design_workflows_do_not_sudo_server_mutable_helper():
    for name in ("operator-design.yml", "trigger-design.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "sudo env INTENT_B64" not in text
        assert "bash /opt/auto-invest/scripts/operator_design.sh" not in text
        assert "< scripts/operator_design.sh" in text


def test_public_sidecar_redaction_covers_publish_directory():
    violations: list[str] = []
    for path, text in _workflow_texts().items():
        if "redact_public_sidecar.py" not in text:
            continue
        if 'redact_public_sidecar.py" LAST_RUN.md' in text:
            violations.append(path.name)
        if 'redact_public_sidecar.py" .' not in text:
            violations.append(f"{path.name}: not directory-wide")
    assert violations == []


def test_decimal_validator_rejects_shell_metacharacters():
    script = REPO_ROOT / "scripts" / "ci_validate_decimal.sh"
    ok = subprocess.run(
        [str(script), "capital", "123.45"],
        capture_output=True,
        text=True,
        check=False,
    )
    bad = subprocess.run(
        [str(script), "capital", "1; touch /tmp/pwned"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0
    assert bad.returncode == 2


def test_provision_capital_input_is_validated_before_userdata_interpolation():
    workflow = (WORKFLOWS / "provision-vultr.yml").read_text(encoding="utf-8")
    build_step = workflow.split("Build cloud-init User-Data", 1)[1]

    assert './scripts/ci_validate_decimal.sh capital "$CAPITAL"' in build_step
    assert build_step.index('ci_validate_decimal.sh capital "$CAPITAL"') < build_step.index(
        'AUTO_INVEST_CAPITAL=\\"${CAPITAL}\\"'
    )


def test_verify_operator_setup_does_not_fail_when_result_files_are_ignored():
    workflow = (WORKFLOWS / "verify-operator-setup.yml").read_text(encoding="utf-8")

    assert "if git add .verify/ 2>/tmp/verify_git_add.err; then" in workflow
    assert "branch-local 결과 commit 을 건너뜁니다" in workflow
    assert "git add -f .verify/" not in workflow


def test_verify_operator_setup_only_fails_manual_verification():
    workflow = (WORKFLOWS / "verify-operator-setup.yml").read_text(encoding="utf-8")

    assert (
        "github.event_name == 'push' && steps.overall.outputs.status != 'all_ok'"
        in workflow
    )
    assert (
        "github.event_name == 'workflow_dispatch' && "
        "steps.overall.outputs.status != 'all_ok'"
        in workflow
    )


def test_verify_operator_setup_uses_gateway_status_command():
    workflow = (WORKFLOWS / "verify-operator-setup.yml").read_text(encoding="utf-8")
    ssh_step = workflow.split("- name: Test SSH connection", 1)[1]

    assert '"status" 2>&1)' in ssh_step
    assert "AUTO_INVEST_GATEWAY_OK" not in workflow  # marker is emitted by the server gateway
    assert "echo SSH_OK" not in ssh_step
    assert "grep -c '^KIS_APP_KEY" not in ssh_step


def test_deploy_workflow_invokes_only_gateway_commands():
    workflow = (WORKFLOWS / "deploy-on-merge.yml").read_text(encoding="utf-8")

    assert '"sync-units"' in workflow
    assert '"start-deploy"' in workflow
    assert '"deploy-journal"' in workflow
    assert "'sudo bash -s'" not in workflow
    assert "sudo systemctl start auto-invest-deploy.service" not in workflow
    assert "sudo journalctl -u auto-invest-deploy.service" not in workflow


def test_live_money_workflows_require_production_environment():
    protected = (
        "go-live-canary.yml",
        "rebalance-live-canary.yml",
        "rebalance-micro-gtaa-canary.yml",
        "release-halt.yml",
    )
    for name in protected:
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "\n    environment: production\n" in workflow


def test_public_sidecar_redactor_masks_sensitive_fields():
    raw = """
| account_no | 1234567801 |
| capital_usd | 12000 |
KIS_APP_SECRET=super-secret-value
bearer abcdefghijklmnopqrstuvwxyz.abcdefghijklmnopqrstuvwxyz.abcdefghijklmnopqrstuvwxyz
host=203.0.113.10
"""
    redacted = _REDACTOR.redact(raw)
    assert "1234567801" not in redacted
    assert "12000" not in redacted
    assert "super-secret-value" not in redacted
    assert "203.0.113.10" not in redacted
    assert "[REDACTED" in redacted


def test_public_sidecar_redactor_masks_json_sensitive_keys():
    raw = {
        "status": "OK",
        "nav_usd": "12345.67",
        "nested": {"kis_order_id": "K-123456", "published": 3},
    }

    redacted = _REDACTOR._redact_json_value(raw)

    assert redacted == {
        "status": "OK",
        "nav_usd": "[REDACTED]",
        "nested": {"kis_order_id": "[REDACTED]", "published": 3},
    }
