"""Deploy audit_log sidecar workflow invariants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-audit-log.yml"


def _body() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_deploy_audit_workflow_is_read_only_on_server() -> None:
    body = _body()

    assert '"deploy-audit"' in body
    assert '"deploy-audit ${requested}"' in body
    assert "AUDIT_TERMINAL_EVENT" in body
    assert "bash -s" not in body
    assert "REQUESTED_CID='" not in body
    assert 'sqlite3 -readonly "${' not in body

    forbidden = [
        "systemctl start",
        "systemctl stop",
        "git reset",
        "auto-invest deploy",
        "auto-invest run",
        "rebalance-once",
    ]
    for fragment in forbidden:
        assert fragment not in body


def test_deploy_audit_workflow_publishes_sidecar() -> None:
    body = _body()

    assert "workflow_dispatch:" in body
    assert "BRANCH=automation/deploy-audit-last-run" in body
    assert "Deploy audit_log verification" in body
    assert "correlation_id" in body


def test_deploy_audit_accepts_only_completed_deploy_or_verified_recovery() -> None:
    body = _body()

    assert "DEPLOY_COMPLETED|DEPLOY_EMERGENCY_RECOVERY_COMPLETED" in body
    assert "not a completed deploy or verified emergency recovery" in body


def test_deploy_audit_validates_optional_correlation_id_before_ssh() -> None:
    body = _body()

    assert "^[0-9a-fA-F]{8,64}$" in body
    assert 'remote_command="deploy-audit"' in body
    assert 'remote_command="deploy-audit ${requested}"' in body
