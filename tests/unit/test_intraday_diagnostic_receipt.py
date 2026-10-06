import copy
import hashlib
import json
import os
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_diagnostic_receipt import (
    SOURCES,
    ReceiptError,
    build_receipt,
    write_receipt,
)

SHA = "d22dea93f3d9740ebdc9f58349d5aa84fc8eb446"
IDENTITY = "f" * 64
NOW = datetime(2026, 10, 6, 15, 48, tzinfo=UTC)


def status():
    return dict(schema_version="1.1", scope="DIAGNOSTIC_PAPER_SERVICE",
                program_readiness="NOT_ASSESSED", status="DIAGNOSTIC_PAPER", identity=IDENTITY,
                observed_at_utc="2026-10-06T15:47:30Z", age_seconds=30.0,
                last_bar="2026-10-06T15:40:00Z", processed_bars=183, simulated_fills=345,
                open_quantity=2206, orders_submitted=0, live_eligible=False,
                forward_promotion_eligible=False, qualified_forward_sessions=0,
                blockers=["DIAGNOSTIC_PAPER_ONLY"], halt_reasons=[])


def raw(s=None, sha=SHA):
    return ("INTRADAY_TIMER=active\nINTRADAY_SERVICE_RESULT=success\n"
            f"INTRADAY_PRODUCTION_COMMIT={sha}\n" + json.dumps(status() if s is None else s))


def build(text):
    return build_receipt(text, source_sha=SHA, run_id="37490472701",
                         identity=IDENTITY, captured=NOW)


def test_original_values_and_distinct_source_are_preserved():
    result = build(raw())
    assert result["diagnostic"]["open_quantity"] == 2206
    assert result["production_commit"] == SHA
    assert result["production_matches_observer_source"] is True
    assert result["diagnostic"]["program_readiness"] == "NOT_ASSESSED"
    assert build(raw(sha="a" * 40))["production_matches_observer_source"] is False


@pytest.mark.parametrize("field,value", [
    ("schema_version", "1.0"), ("source_schema_version", "1.0"),
    ("scope", "LIVE_ACCOUNT"), ("program_readiness", "COMPLETE"), ("status", "FAILED"),
    ("orders_submitted", 1), ("orders_submitted", False), ("qualified_forward_sessions", 1),
    ("qualified_forward_sessions", False), ("live_eligible", True), ("live_eligible", 0),
    ("forward_promotion_eligible", True), ("identity", "a" * 64),
    ("open_quantity", "22***"), ("open_quantity", True), ("open_quantity", -1),
    ("simulated_fills", 1.5), ("processed_bars", 2**63),
    ("age_seconds", float("nan")), ("age_seconds", float("inf")),
    ("age_seconds", 181), ("age_seconds", -1), ("age_seconds", True),
    ("observed_at_utc", "2026-10-06T15:48:01Z"),
    ("observed_at_utc", "2026-10-06T15:44:59Z"),
    ("observed_at_utc", "2026-10-06T15:47:30"),
    ("last_bar", "2026-10-06T15:45:00Z"),
    ("last_bar", "2026-10-06T15:41:00Z"),
    ("blockers", ["secret@example.com"]), ("halt_reasons", ["price=123"]),
    ("archived_session", "../private"), ("archive_status", "price 123"),
    ("archived_session", "2026-10-07"),
])
def test_bad_or_authority_claiming_input_is_rejected(field, value):
    s = copy.deepcopy(status())
    s[field] = value
    with pytest.raises(ReceiptError):
        build(raw(s))


@pytest.mark.parametrize("text", [
    raw().replace(SHA, "d***dea93"),
    raw().replace("INTRADAY_TIMER=active", "INTRADAY_TIMER=inactive"),
    raw() + "\nINTRADAY_TIMER=active",
    raw().replace('"open_quantity": 2206', '"open_quantity": 2206, "open_quantity": 9'),
    "x" * 65537,
    raw().replace("INTRADAY_TIMER=active", "INTRADAY_TIMER=active\nINTRADAY_TIMER=active"),
])
def test_masked_duplicate_partial_or_large_envelope_rejected(text):
    with pytest.raises(ReceiptError):
        build(text)


def test_unknown_private_fields_are_not_exported():
    s = status()
    s.update(account="private-account", appsecret="PRIVATE_KEY_VALUE", price=123.45)
    result = build(raw(s))
    encoded = json.dumps(result)
    assert "private-account" not in encoded and "PRIVATE_KEY_VALUE" not in encoded
    assert '"price"' not in encoded and '"account"' not in encoded


def test_wait_session_and_archive_are_diagnostic_only():
    s = status()
    s.update(status="WAIT_SESSION", last_bar=None, archived_session="2026-10-05",
             archive_status="COMPLETE", open_quantity=0)
    result = build(raw(s))
    assert result["diagnostic"]["archive_status"] == "COMPLETE"
    assert result["diagnostic"]["live_eligible"] is False


def test_new_file_only_and_symlink_refused(tmp_path):
    report = build(raw())
    path = tmp_path / "report.json"
    write_receipt(path, report)
    first = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_receipt(path, report)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(FileExistsError):
        write_receipt(link, report)
    assert path.read_bytes() == first


def test_wait_without_database_preserves_unknown_counts():
    s = status()
    s["status"] = "WAIT_SESSION"
    for key in ("processed_bars", "simulated_fills", "open_quantity", "halt_reasons"):
        del s[key]
    s["last_bar"] = None
    result = build(raw(s))["diagnostic"]
    assert "open_quantity" not in result and "simulated_fills" not in result
    assert result["orders_submitted"] == 0


@pytest.mark.parametrize("field", ["processed_bars", "simulated_fills", "open_quantity",
                                  "halt_reasons"])
def test_active_cycle_requires_observed_counts(field):
    s = status()
    del s[field]
    with pytest.raises(ReceiptError):
        build(raw(s))


@pytest.mark.parametrize("scenario", ["valid", "wrong_identity", "masked", "symlink",
                                    "existing_output", "wrong_source"])
def test_cli_real_entrypoint_and_safe_failure(tmp_path, scenario):
    s = status()
    hashes = ["sha256:" + hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES]
    s["identity"] = hashlib.sha256(json.dumps(hashes, separators=(",", ":")).encode()).hexdigest()
    s["observed_at_utc"] = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
    s["last_bar"] = None
    s["account"] = "PRIVATE_ACCOUNT_VALUE"
    source = tmp_path / "source.txt"
    target = tmp_path / "report.json"
    if scenario == "wrong_identity":
        s["identity"] = "a" * 64
    text = raw(s)
    if scenario == "masked":
        text = text.replace('"open_quantity": 2206', '"open_quantity": ***06')
    source.write_text(text)
    if scenario == "symlink":
        link = tmp_path / "link.txt"
        link.symlink_to(source)
        source = link
    if scenario == "existing_output":
        target.write_text("preserved")
    command = [sys.executable, "-m", "auto_invest.analytics.intraday_diagnostic_receipt",
               "--input", str(source), "--output", str(target), "--source-sha",
               "invalid" if scenario == "wrong_source" else SHA, "--run-id", "123"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert "PRIVATE_ACCOUNT_VALUE" not in result.stdout + result.stderr
    if scenario == "valid":
        assert result.returncode == 0
        receipt = json.loads(target.read_text())
        assert receipt["diagnostic"]["open_quantity"] == 2206
        assert "PRIVATE_ACCOUNT_VALUE" not in target.read_text()
    else:
        assert result.returncode == 1 and result.stdout.strip() == "DIAGNOSTIC_RECEIPT_INVALID"
        if scenario == "existing_output":
            assert target.read_text() == "preserved"
        else:
            assert not target.exists()


@pytest.mark.parametrize("ssh_exit", [0, 42])
def test_actual_workflow_read_step_keeps_transport_failure(tmp_path, ssh_exit):
    workflow = Path(".github/workflows/intraday-paper-status.yml").read_text()
    step = workflow.split("      - name: Read diagnostic status only\n")[1]
    script = textwrap.dedent(step.split("        run: |\n")[1].split("      - name:")[0])
    script = script.replace("/tmp/intraday-status.txt", str(tmp_path / "status.txt"))
    s = status()
    hashes = ["sha256:" + hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES]
    s["identity"] = hashlib.sha256(json.dumps(hashes, separators=(",", ":")).encode()).hexdigest()
    env = dict(os.environ, HOST="synthetic-host", USER="synthetic-user", PORT="22",
               TEST_STDOUT=raw(s), TEST_SSH_EXIT=str(ssh_exit))
    # The actual checked-in shell step runs; no network command or credentials are used.
    fake = 'ssh() { printf "%s\\n" "$TEST_STDOUT"; return "$TEST_SSH_EXIT"; }\n'
    result = subprocess.run(["bash", "-e", "-c", fake + script], env=env,
                            capture_output=True, text=True, timeout=15)
    assert (result.returncode == 0) is (ssh_exit == 0)
