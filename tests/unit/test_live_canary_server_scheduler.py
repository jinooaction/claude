"""Spec 176: independent production live-canary scheduler safety contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
SERVICE = DEPLOY / "auto-invest-live-canary.service"
TIMER = DEPLOY / "auto-invest-live-canary.timer"
SCHEDULER = DEPLOY / "live-canary-scheduled-on-instance.sh"


def _active(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_root_owned_service_and_new_york_fallback_timer_are_declared() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    timer = TIMER.read_text(encoding="utf-8")

    assert "User=root" in service
    assert "Group=root" in service
    assert "ExecStart=/usr/local/sbin/auto-invest-live-canary-scheduler" in service
    assert "RefuseManualStart=yes" in service
    assert "UMask=0077" in service
    assert "EnvironmentFile=" not in _active(service)
    assert "Persistent=false" in timer
    assert "Requires=auto-invest-live-canary.service" not in timer
    assert "America/New_York" in timer
    assert "10:35:00" in timer
    assert "13:59:00" in timer
    assert "10:17:00" not in timer
    assert ":00:00 America/New_York" not in timer
    candidates = re.findall(
        r"^OnCalendar=Mon\.\.Fri \*-\*-\* (\d{2}:\d{2}):00 America/New_York$",
        timer,
        flags=re.MULTILINE,
    )
    assert candidates == [
        "10:35",
        "10:47",
        "10:59",
        "11:11",
        "11:23",
        "11:35",
        "11:47",
        "11:59",
        "12:11",
        "12:23",
        "12:35",
        "12:47",
        "12:59",
        "13:11",
        "13:23",
        "13:35",
        "13:47",
        "13:59",
    ]


def test_scheduler_fails_closed_before_shared_claim() -> None:
    body = SCHEDULER.read_text(encoding="utf-8")
    main = body.split("\nmain() {", 1)[1]

    root_idx = main.index("require_root_systemd")
    exact_idx = main.index("validate_operational_revision")
    deploy_idx = main.index('validate_deploy_audit "${deployed_sha}"')
    market_idx = main.index("validate_market_session")
    duplicate_idx = main.index("existing_session_claim")
    entry_idx = main.index("run_entry_revalidation")
    order_idx = main.index('systemd-order "${run_id}"')
    assert root_idx < exact_idx < deploy_idx < market_idx < duplicate_idx < entry_idx < order_idx
    assert "INVOCATION_ID" in body
    assert "/proc/self/cgroup" in body
    assert "auto-invest-live-canary\\.service" in body
    assert "live_entry_revalidation_probe.py" in body
    assert "live-canary-backfill" in body
    assert "--expected-code-commit" in body
    assert "live-canary-preview" in body
    assert "execution-proxy-parity" in body
    assert "exploration-canary" in body
    assert "automation/AUTOARM_DISABLED" in body
    assert "systemctl is-active --quiet auto-invest.service" in body
    assert "DEPLOY_COMPLETED" in body
    assert "sqlite3 -readonly" in body
    assert "python -m auto_invest.execution.live_session" in body
    assert "flock -s" in body
    assert "LIVE_CANARY_SERVER_TIMER_DUPLICATE" in body


def test_scheduler_checks_deploy_maintenance_before_session_claim() -> None:
    body = SCHEDULER.read_text(encoding="utf-8")
    main = body.split("\nmain() {", 1)[1]

    interlock_idx = main.index("refuse_deploy_maintenance")
    market_idx = main.index("validate_market_session")
    claim_idx = main.index("existing_session_claim")
    assert interlock_idx < market_idx < claim_idx
    assert "/run/auto-invest-deploy/live-order-maintenance.lock" in body


def test_scheduler_preserves_post_attempt_evidence_without_retrying() -> None:
    body = SCHEDULER.read_text(encoding="utf-8")

    assert "LIVE_ORDER_SESSION_ALREADY_CLAIMED" in body
    assert '"${LIVE_HELPER}" fills' in body
    assert '"${OBSERVE_HELPER}" live-canary-measure' in body
    assert '"${LIVE_HELPER}" profit' in body
    assert '"${RECONCILIATION_HELPER}"' in body
    assert "scheduled-runs" in body
    assert "summary.json" in body
    assert "last-scheduled-run-id" in body
    assert "orders_submitted" in body
    assert "SUBMITTED|PARTIALLY_FILLED|FILLED|SUBMISSION_UNKNOWN" in body
    assert "source" in body and "server_timer" in body
    assert "market order" not in body.lower()
    assert "--mode live" not in body
    assert "--confirm-live" not in body


def test_remote_gateway_exposes_status_but_not_systemd_order() -> None:
    repair = (DEPLOY / "repair-ssh-boundary.sh").read_text(encoding="utf-8")
    gateway = repair.split("EOF_GATEWAY", 2)[1]

    assert "live-canary-scheduled-status)" in gateway
    assert "live-canary-scheduled-status\\ *)" in gateway
    assert "^[0-9]{14}$" in gateway
    assert "scheduled-status" in gateway
    assert "systemd-order" not in gateway
