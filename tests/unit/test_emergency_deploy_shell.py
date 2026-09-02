"""Spec 179: root helper, forced command, workflow, and interlock contract."""

from __future__ import annotations

import json
import subprocess
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
    assert "prepare_exact_target_runner" in body
    assert '/usr/local/bin/uv run --project "${bootstrap_repo}" auto-invest deploy' in body
    assert '--repo "${REPO}"' in body
    assert '--db "${DB_PATH}"' in body
    assert '--health-window-s 90' in body
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
    assert body.index("systemctl stop auto-invest.service") < body.rindex(
        '"${KIS_SMOKE_HELPER}"'
    )
    assert body.rindex('"${KIS_SMOKE_HELPER}"') < body.index(
        'prepare_exact_target_runner "${target_sha}"'
    )


def test_prestart_halted_recovery_is_closed_and_audit_bound() -> None:
    body = HELPER.read_text(encoding="utf-8")
    assert "validate_halted_interlock_for_recovery" in body
    assert 'state == "HALTED"' in body
    assert 'reason == "deploy terminal safety not proven"' in body
    assert 'event_type = \'DEPLOY_EMERGENCY_AUTHORIZED\'' in body
    assert 'event_type = \'DEPLOY_STARTED\'' in body
    assert '"${started_count}" != "0"' in body
    assert '"${deploy_row_count}" == "1"' in body
    assert '"${deploy_row_count}" == "2"' in body
    assert '"${orphan_recovered_count}" == "1"' in body
    assert "$.completed_deploy_correlation_id" in body
    assert "$.recovered_production_sha" in body
    assert "existing maintenance interlock is still owned" in body


def test_terminal_rollback_orphan_recovery_is_closed_and_audit_bound() -> None:
    body = HELPER.read_text(encoding="utf-8")
    assert "validate_terminal_rollback_orphan" in body
    assert 'state == "QUIESCED"' in body
    assert '"${request_meta}" == "0:${expected_gid}:640"' in body
    assert '"${started_count}" == "1"' in body
    assert '"${failed_count}" == "1"' in body
    assert '"${rolled_back_count}" == "1"' in body
    assert '"${completed_count}" == "0"' in body
    assert '"${unexpected_count}" == "0"' in body
    assert '"${terminal_event}" == "DEPLOY_ROLLED_BACK"' in body
    assert '"${production_head}" == "${rollback_sha_before}"' in body
    assert '"${production_head}" == "${authorized_target_sha}"' in body
    assert 'rollback_recovery_mode="completed-deploy"' in body
    assert "merge-base --is-ancestor" in body
    assert '"${deploy_started_count}" == "1"' in body
    assert '"${deploy_completed_count}" == "1"' in body
    assert '"${deploy_failed_count}" == "0"' in body
    assert '"${deploy_rolled_back_count}" == "0"' in body
    assert '"${deploy_terminal_event}" == "DEPLOY_COMPLETED"' in body
    assert "worker_started_count" in body
    assert "systemctl is-active --quiet auto-invest.service" in body
    assert "systemctl is-active --quiet auto-invest-live-canary.timer" in body
    assert "append_recovery_completed" in body
    assert "DEPLOY_EMERGENCY_RECOVERY_COMPLETED" in body
    assert "DEPLOY_EMERGENCY_INTERLOCK_PRESERVED" in body
    assert body.index("validate_terminal_rollback_orphan") < body.index(
        'rm -f "${REQUEST_PATH}"'
    )
    assert body.count("trap - EXIT") == 3


def test_forward_recovery_handoff_is_ancestry_audit_and_broker_bound() -> None:
    body = HELPER.read_text(encoding="utf-8")
    assert "RECOVERING_POSTROLLBACK_FORWARD_HANDOFF" in body
    assert '"${rollback_sha_before}" "${production_head}"' in body
    assert '"${production_head}" "${authorized_target_sha}"' in body
    assert "validated_recovery_production_sha" in body
    assert 'rollback_recovery_mode="completed-deploy-handoff"' in body
    assert "append_orphan_recovered" in body
    assert "DEPLOY_EMERGENCY_ORPHAN_RECOVERED" in body
    assert "subsequent-live-deploy-forward-handoff" in body
    assert "forward_handoff_authorized" in body

    handoff = body.split(
        'flock -w 30 -x 8 || die "live broker write did not quiesce within 30 seconds"',
        1,
    )[1]
    assert handoff.index('"${KIS_SMOKE_HELPER}"') < handoff.index(
        'append_orphan_recovered \\'
    )
    assert handoff.index('append_orphan_recovered \\') < handoff.index(
        'rm -f "${REQUEST_PATH}" "${smoke_tmp}"'
    )
    assert handoff.index('DEPLOY_EMERGENCY_ORPHAN_RECOVERED') < handoff.index(
        'prepare_exact_target_runner "${target_sha}"'
    )


def test_exact_deployed_target_without_stale_state_is_no_mutation_noop() -> None:
    body = HELPER.read_text(encoding="utf-8")
    marker = "DEPLOY_EMERGENCY_NOT_NEEDED"
    assert marker in body
    assert body.index(marker) < body.index("install -d -m 0700")
    assert body.index(marker) < body.index(
        'authorization_correlation_id="$(append_preauthorization'
    )


def test_owner_workflow_always_delegates_stale_state_decision_to_root_helper() -> None:
    body = WORKFLOW.read_text(encoding="utf-8")
    assert "Normal deploy already completed; emergency exception was not consumed." not in body
    assert 'if [[ "${START_EXIT}" != "0"' in body
    assert "current_stale_target_refusal" in body
    assert "emergency request target does not match current main" in body
    assert "emergency-deploy ${GITHUB_SHA}" in body
    assert "DEPLOY_EMERGENCY_NOT_NEEDED" in body


def test_workflow_classifies_only_the_current_deploy_attempt_journal() -> None:
    body = WORKFLOW.read_text(encoding="utf-8")
    assert "deploy_current_journal.txt" in body
    assert "Starting auto-invest deploy automation \\(one-shot\\)" in body
    assert 'grep -qiE \'market is open|market_hours_guard\' "${current_journal}"' in body
    assert 'grep -qiE \'market is open|market_hours_guard\' <<<"${current_journal}"' in body
    assert (
        "grep -qiE 'market is open|market_hours_guard' "
        "/tmp/deploy_journal.txt"
    ) not in body


def test_current_attempt_extractor_discards_historical_market_refusal() -> None:
    body = WORKFLOW.read_text(encoding="utf-8")
    marker = "          awk '\n"
    start = body.index(marker) + len(marker)
    end = body.index("\n          ' /tmp/deploy_journal.txt", start)
    awk_program = body[start:end]
    journal = "\n".join(
        (
            "Sep 02 19:54 systemd: Starting auto-invest deploy automation (one-shot)...",
            "Sep 02 19:54 worker: deploy refused: US market is open",
            "Sep 02 19:54 systemd: Failed to start auto-invest deploy automation (one-shot).",
            "Sep 02 20:53 systemd: Starting auto-invest deploy automation (one-shot)...",
            "Sep 02 20:53 worker: deploy refused: market closed; "
            "emergency request target does not match current main",
            "Sep 02 20:53 systemd: Failed to start auto-invest deploy automation (one-shot).",
        )
    )

    result = subprocess.run(
        ["awk", awk_program],
        input=journal,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "US market is open" not in result.stdout
    assert "emergency request target does not match current main" in result.stdout


def test_terminal_rollback_request_filter_executes_in_object_scope() -> None:
    body = HELPER.read_text(encoding="utf-8")
    scope_marker = "        . as $request |\n"
    marker_index = body.index(scope_marker)
    filter_start = body.rfind("    jq -e '\n", 0, marker_index) + len("    jq -e '\n")
    filter_end = body.index("\n    ' \"${REQUEST_PATH}\"", marker_index)
    request_filter = body[filter_start:filter_end]
    payload = {
        "schema_version": "1.0",
        "request_id": "github-run-33673819722",
        "target_sha": "e" * 40,
        "actor": "masonoh-kidsnote",
        "workflow_run_id": "33673819722",
        "source": "github-actions-workflow-dispatch",
        "reason_sha256": "a" * 64,
        "issued_at_epoch": 1788377519,
        "expires_at_epoch": 1788378119,
    }

    valid = subprocess.run(
        ["jq", "-e", request_filter],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stderr

    payload["expires_at_epoch"] = payload["issued_at_epoch"]
    expired = subprocess.run(
        ["jq", "-e", request_filter],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert expired.returncode != 0


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
