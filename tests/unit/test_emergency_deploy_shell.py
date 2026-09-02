"""Spec 179: root helper, forced command, workflow, and interlock contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "deploy" / "emergency-deploy-on-instance.sh"
REPAIR = ROOT / "deploy" / "repair-ssh-boundary.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-on-merge.yml"
LIVE = ROOT / "deploy" / "live-canary-on-instance.sh"
SCHEDULED = ROOT / "deploy" / "live-canary-scheduled-on-instance.sh"
ROUTER = ROOT / "src" / "auto_invest" / "execution" / "order_router.py"


def test_root_helper_is_fixed_one_shot_and_preserves_failed_interlock() -> None:
    assert HELPER.is_file()
    body = HELPER.read_text(encoding="utf-8")
    assert "require_root" in body
    assert "readonly MAX_TTL_SEC=900" in body
    assert "open_unfilled=0" in body
    assert "/usr/local/sbin/auto-invest-kis-smoke" in body
    assert "/run/auto-invest-deploy/emergency-request.json" in body
    assert "/run/auto-invest-deploy/live-order-maintenance.lock" in body
    assert "/run/auto-invest-deploy/broker-write.lock" in body
    assert "flock -w 30 -x 8" in body
    assert "INSERT INTO audit_log" in body
    assert "systemctl stop auto-invest-live-canary.timer" in body
    assert "systemctl stop auto-invest-live-canary.service" in body
    assert "systemctl stop auto-invest.service" in body
    assert "systemctl start auto-invest-live-canary.timer" in body
    assert "systemctl start auto-invest-deploy.service" in body
    assert "install -m 0640 -o root -g" in body
    assert "DEPLOY_EMERGENCY_HALTED" in body
    assert "rm -f" in body
    assert "eval " not in body
    assert "bash -c" not in body
    assert "pgrep" in body and "rebalance-once" in body
    assert "live-canary-order" not in body
    assert '${REPO:-' not in body
    assert '${DB_PATH:-' not in body
    assert body.index("INSERT INTO audit_log") < body.index(
        "systemctl stop auto-invest.service"
    )
    assert body.index("systemctl stop auto-invest.service") < body.index(
        '"${KIS_SMOKE_HELPER}"'
    )
    assert body.index('"${KIS_SMOKE_HELPER}"') < body.index(
        "systemctl start auto-invest-deploy.service"
    )


def test_forced_gateway_exposes_only_validated_emergency_deploy() -> None:
    body = REPAIR.read_text(encoding="utf-8")
    gateway = body.split("EOF_GATEWAY", 2)[1]
    assert "emergency-deploy\\ *" in gateway
    assert "/usr/local/sbin/auto-invest-emergency-deploy" in gateway
    assert '"${target_sha}" "${workflow_run_id}" "${actor}"' in gateway
    assert '"${issued_at}" "${expires_at}" "${reason_sha256}"' in gateway
    assert "^[0-9a-f]{40}$" in gateway
    assert "^[1-9][0-9]*$" in gateway
    assert "^[0-9a-f]{64}$" in gateway
    assert "eval " not in gateway
    assert "bash -c" not in gateway


def test_workflow_emergency_is_registered_owner_exact_main_confirmed_and_short_lived() -> None:
    body = WORKFLOW.read_text(encoding="utf-8")
    assert "owner_emergency" in body
    assert "OWNER_EMERGENCY_LIVE_DEPLOY" in body
    assert "github.actor" in body and "github.repository_owner" in body
    assert "REGISTERED_SYSTEM_OWNER: masonoh-kidsnote" in body
    assert '${REGISTERED_SYSTEM_OWNER}' in body
    assert "vars." not in body
    assert "github.event_name == 'workflow_dispatch'" in body
    assert "expected_sha" in body
    assert "reason_sha256" in body
    assert "expires_at" in body
    assert "emergency-deploy ${GITHUB_SHA}" in body
    assert "repository_dispatch" not in body
    assert "live-canary-order" not in body
    assert "market is open|market_hours_guard|emergency_authorization" not in body
    owner_success_guard = (
        "steps.owner_emergency.outcome == 'success'"
    )
    assert body.count(owner_success_guard) >= 3


def test_workflow_does_not_accept_owner_identity_as_runtime_input() -> None:
    body = WORKFLOW.read_text(encoding="utf-8")
    inputs = body.split("permissions:", 1)[0]
    assert "system_owner" not in inputs
    assert "owner_actor" not in inputs
    assert "authorized_actor" not in inputs


def test_all_three_broker_write_boundaries_check_maintenance_interlock() -> None:
    live = LIVE.read_text(encoding="utf-8")
    scheduled = SCHEDULED.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    marker = "live-order-maintenance.lock"
    assert marker in live
    assert "/run/auto-invest-deploy/broker-write.lock" in live
    assert "flock -n -s 7" in live
    assert live.index(marker) < live.index("claim_order_session")
    assert marker in scheduled
    assert scheduled.index(marker) < scheduled.index("existing_session_claim")
    authority = (ROOT / "src" / "auto_invest" / "execution" / "authority.py").read_text(
        encoding="utf-8"
    )
    assert marker in authority
    assert "maintenance_interlock_refusal" in router
    assert router.index("maintenance_interlock_refusal") < router.index(
        "submit_broker_order"
    )
