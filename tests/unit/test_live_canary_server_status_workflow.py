"""Read-only server timer observation workflow invariants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "live-canary-server-status.yml"


def _body() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_server_status_workflow_has_only_manual_read_trigger() -> None:
    body = _body()

    assert "workflow_dispatch:" in body
    assert "schedule:" not in body
    assert "\n  push:" not in body
    assert 'remote_command="live-canary-scheduled-status"' in body
    assert 'remote_command="live-canary-scheduled-status ${requested}"' in body
    assert '"live-canary-runtime-status"' in body
    assert '"live-canary-scheduled-order-diagnostics ${SERVER_RUN_ID}"' in body
    assert "^[0-9]{14}$" in body


def test_server_status_workflow_cannot_write_to_broker_or_service() -> None:
    body = _body()

    forbidden = [
        "live-canary-systemd-order",
        "rebalance-once",
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "bash -s",
        "--confirm-live",
    ]
    for fragment in forbidden:
        assert fragment not in body


def test_server_status_workflow_validates_and_sanitizes_before_publish() -> None:
    body = _body()

    assert '.schema_version == "1.1"' in body
    assert '--arg requested "${requested}"' in body
    assert '($requested == "" or .run_id == $requested)' in body
    assert '.source == "server_timer"' in body
    assert ".operational_equivalent == true" in body
    assert '((keys | sort) == ([' in body
    assert "scripts/redact_public_sidecar.py" in body
    assert "BRANCH=automation/" not in body
    assert "branch=automation/live-canary-server-status-last-run" in body
    assert "server_scheduled_status.json" in body
    assert "server_runtime_status.json" in body
    assert "server_order_diagnostics.json" in body
    assert '.source == "server_timer_runtime"' in body
    assert '((.timer | keys | sort) == ([' in body
    assert '((.service | keys | sort) == ([' in body
    assert '.source == "server_timer_order_diagnostics"' in body
    assert '.schema_version == "1.1"' in body
    assert '"broker_rejections"' in body
    assert '"kis_msg_cd"' in body
    assert '"order_exchange"' in body
    assert "diagnostic_status=invalid_diagnostics" in body


def test_server_status_workflow_fails_closed_without_valid_summary() -> None:
    body = _body()

    assert "query_status=invalid_input" in body
    assert "query_status=unavailable" in body
    assert "query_status=invalid_summary" in body
    assert "runtime_status=ok" in body
    assert "runtime_status=invalid_runtime" in body
    assert "valid server timer summary was not observed" in body
    assert '"${QUERY_EXIT:-1}" != "0"' in body
    assert '"${QUERY_STATUS:-}" != "ok"' in body
    assert "zero-order run lacks valid sanitized diagnostics" in body
    assert '"${DIAGNOSTIC_STATUS:-}" != "ok"' in body
