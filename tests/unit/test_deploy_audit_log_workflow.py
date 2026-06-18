"""Deploy audit_log sidecar workflow invariants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-audit-log.yml"


def _body() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_deploy_audit_workflow_is_read_only_on_server() -> None:
    body = _body()

    assert "sqlite3 -readonly" in body
    assert "event_type LIKE 'DEPLOY_%'" in body
    assert "AUDIT_TERMINAL_EVENT" in body

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


def test_deploy_audit_fails_unless_terminal_completed() -> None:
    body = _body()

    assert 'AUDIT_TERMINAL:-}" != "DEPLOY_COMPLETED"' in body
    assert "latest deploy audit terminal event" in body
