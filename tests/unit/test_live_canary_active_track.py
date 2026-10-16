"""Existing live fills remain subject to the same scheduler/risk boundaries."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from auto_invest.portfolio.live_entry_revalidation import evaluate_live_entry

ROOT = Path(__file__).resolve().parents[2]
SCHEDULER = ROOT / "deploy/live-canary-scheduled-on-instance.sh"


def _evaluate_shell(tmp_path: Path, payload: dict, probe_exit: int = 0):
    response = tmp_path / "response.json"
    response.write_text(json.dumps(payload), encoding="utf-8")
    helper = tmp_path / "observe"
    helper.write_text("#!/bin/sh\nprintf '{}\\n'\n", encoding="utf-8")
    helper.chmod(0o700)
    work = tmp_path / "work"
    work.mkdir()
    source = SCHEDULER.read_text().rsplit('\nmain "$@"', 1)[0]
    harness = source + r'''
git_as_app() {
    case "$1" in
        fetch) return 0 ;;
        show)
            if [[ "${2:-}" == "-s" ]]; then date +%s; else printf '{}\n'; fi ;;
        *) return 99 ;;
    esac
}
run_as_app() {
    cat "${TEST_RESPONSE}"
    return "${TEST_PROBE_EXIT}"
}
run_entry_revalidation aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 143 "${TEST_WORK}" || exit $?
printf 'accepted_state=%s\n' "${ENTRY_REVALIDATION_STATE:-unset}"
'''
    return subprocess.run(
        ["bash"], input=harness, text=True, capture_output=True, check=False,
        env={**os.environ, "REPO": str(tmp_path),
             "OBSERVE_HELPER": str(helper), "LIVE_HELPER": str(helper),
             "TEST_RESPONSE": str(response), "TEST_WORK": str(work),
             "TEST_PROBE_EXIT": str(probe_exit)},
    )


def test_real_producer_active_track_is_accepted_without_broker_calls(tmp_path):
    payload = evaluate_live_entry(
        None, None, {"fills_count": 2}, evidence_age_hours=None,
    ).as_dict()
    assert payload["state"] == "ACTIVE_LIVE_TRACK"
    result = _evaluate_shell(tmp_path, payload)
    assert result.returncode == 0, result.stderr
    assert "accepted_state=ACTIVE_LIVE_TRACK" in result.stdout


@pytest.mark.parametrize(
    "state,allowed,count,probe_exit,accepted",
    [
        ("ENTRY_READY", True, 0, 0, True),
        ("ACTIVE_LIVE_TRACK", True, 1, 0, True),
        ("ACTIVE_LIVE_TRACK", False, 1, 0, False),
        ("ACTIVE_LIVE_TRACK", "true", 1, 0, False),
        ("ACTIVE_LIVE_TRACK", True, 0, 0, False),
        ("ENTRY_READY", True, 1, 0, False),
        ("ENTRY_BLOCKED", True, 0, 0, False),
        ("NEW_STATE", True, 2, 0, False),
        ("ACTIVE_LIVE_TRACK", True, -1, 0, False),
        ("ACTIVE_LIVE_TRACK", True, 1.5, 0, False),
        ("ACTIVE_LIVE_TRACK", True, True, 0, False),
        ("ACTIVE_LIVE_TRACK", True, "2", 0, False),
        ("ACTIVE_LIVE_TRACK", True, None, 0, False),
        ("ACTIVE_LIVE_TRACK", True, 2, 3, False),
    ],
)
def test_scheduler_revalidation_contract(
    tmp_path, state, allowed, count, probe_exit, accepted,
):
    payload = {"schema_version": "1.0", "state": state,
               "allowed": allowed, "fills_count": count}
    result = _evaluate_shell(tmp_path, payload, probe_exit)
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr
    if accepted:
        assert f"accepted_state={state}" in result.stdout


@pytest.mark.parametrize("schema", [None, "2.0", 1])
def test_unknown_or_missing_probe_schema_is_rejected(tmp_path, schema):
    payload = {"state": "ACTIVE_LIVE_TRACK", "allowed": True, "fills_count": 2}
    if schema is not None:
        payload["schema_version"] = schema
    assert _evaluate_shell(tmp_path, payload).returncode != 0


def test_summary_records_actual_state_and_retry_contract_stays_first_entry_only():
    scheduler = SCHEDULER.read_text()
    assert '--arg entry_state "${ENTRY_REVALIDATION_STATE}"' in scheduler
    assert '--arg entry_state "ENTRY_READY"' not in scheduler
    helper = (ROOT / "deploy/live-canary-on-instance.sh").read_text()
    retry = helper.split("claim_same_session_retry() {", 1)[1].split(
        "\n}", 1
    )[0]
    assert '.entry_state == "ENTRY_READY"' in retry
    assert "ACTIVE_LIVE_TRACK" not in retry


@pytest.mark.parametrize(
    "state,expected", [("ENTRY_READY", 0), ("ACTIVE_LIVE_TRACK", 0),
                       ("ENTRY_BLOCKED", 1), ("OTHER", 1)],
)
def test_actual_observer_filter_accepts_only_known_entry_states(state, expected):
    workflow = (ROOT / ".github/workflows/live-canary-server-status.yml").read_text()
    marker = '          if ! jq -e --arg requested "${requested}" \'\n'
    expression = workflow.split(marker, 1)[1].split(
        "' /tmp/live_canary_server_summary.json", 1
    )[0]
    payload = {
        "schema_version": "1.1", "run_id": "20260908143507",
        "source": "server_timer", "market_session": "2026-09-08",
        "started_at_utc": "2026-09-08T14:35:07Z",
        "finished_at_utc": "2026-09-08T14:37:33Z",
        "code_commit": "a" * 40, "deployed_code_commit": "a" * 40,
        "operational_equivalent": True, "capital_usd": "143",
        "entry_state": state, "entry_allowed": True, "claim_status": "claimed",
        "order_exit": 0, "orders_submitted": 1, "fills_exit": 0,
        "measurement_exit": 0, "reconciliation_exit": 0, "result": "completed",
    }
    result = subprocess.run(
        ["jq", "-e", "--arg", "requested", "", expression],
        input=json.dumps(payload), text=True, capture_output=True, check=False,
    )
    assert result.returncode == expected, result.stderr

