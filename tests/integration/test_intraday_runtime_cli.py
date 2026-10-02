import json
import os
import subprocess
import sys

import pytest


def test_cli_no_credentials_is_explicit_and_redacted(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("APCA_", "KIS_"))}
    result = subprocess.run(
        [
            sys.executable,
            "scripts/intraday_runtime.py",
            "collect",
            "--provider",
            "alpaca",
            "--start",
            "2023-01-01T00:00:00Z",
            "--end",
            "2026-09-01T00:00:00Z",
            "--out",
            str(tmp_path / "batch"),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    status = json.loads(result.stdout)
    assert status["status"] == "DATA_ACCESS_REQUIRED"
    assert status["orders_submitted"] == 0
    assert not (tmp_path / "batch").exists()


def test_cli_live_not_an_option_and_status_never_creates_db(tmp_path):
    path = tmp_path / "state.db"
    result = subprocess.run(
        [sys.executable, "scripts/intraday_runtime.py", "status", "--state", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert not path.exists()
    result = subprocess.run(
        [sys.executable, "scripts/intraday_runtime.py", "live"], capture_output=True, text=True
    )
    assert result.returncode == 2


def test_cli_paper_replay_and_status_are_connected(tmp_path):
    from datetime import UTC, datetime, timedelta

    from auto_invest.market_data.intraday import SYMBOLS, iso, write_batch

    opening = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)
    rows = []
    for n in range(78):
        for symbol in SYMBOLS:
            rows.append(
                dict(
                    symbol=symbol,
                    timestamp_utc=iso(opening + timedelta(minutes=5 * n)),
                    open=100 + n * 0.1,
                    high=102 + n * 0.1,
                    low=99 + n * 0.1,
                    close=100.5 + n * 0.1,
                    volume=100000,
                )
            )
    batch = dict(
        provider="synthetic-cli-test",
        synthetic=True,
        retrieved_at_utc="2026-09-04T21:00:00Z",
        bars=rows,
        pages=[],
    )
    write_batch(tmp_path / "batch", batch)
    command = [
        sys.executable,
        "scripts/intraday_runtime.py",
        "paper",
        "--bars-dir",
        str(tmp_path / "batch"),
        "--state",
        str(tmp_path / "paper.db"),
    ]
    outputs = []
    for _ in range(2):
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1]
    assert outputs[0]["processed_bars"] == 78
    assert outputs[0]["simulated_fills"] > 0
    assert outputs[0]["forward_promotion_eligible"] is False
    result = subprocess.run(
        [
            sys.executable,
            "scripts/intraday_runtime.py",
            "status",
            "--state",
            str(tmp_path / "paper.db"),
        ],
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == outputs[0]


@pytest.mark.parametrize("legacy", [False, True])
def test_service_status_cli_keeps_scope_and_read_only_legacy_contract(tmp_path, legacy):
    from datetime import UTC, datetime

    from auto_invest.analytics.intraday_service import publish

    value = publish(tmp_path, dict(status="WAIT_SESSION"), datetime.now(UTC))
    if legacy:
        value["schema_version"] = "1.0"
        value.pop("scope", None)
        value.pop("program_readiness", None)
        value["blockers"] = [
            "HISTORY_756_SESSIONS_REQUIRED", "HISTORICAL_ACCEPTANCE_REQUIRED",
            "QUALIFIED_FORWARD_60_SESSIONS_REQUIRED", "PROVIDER_EXECUTION_PARITY_REQUIRED",
            "LIVE_ADAPTER_NOT_IMPLEMENTED", "PRODUCTION_FILLS_NOT_VERIFIED",
        ]
        (tmp_path / "status.json").write_text(json.dumps(value))
    original = (tmp_path / "status.json").read_bytes()
    result = subprocess.run(
        [sys.executable, "scripts/intraday_runtime.py", "service-status",
         "--service-root", str(tmp_path)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["scope"] == "DIAGNOSTIC_PAPER_SERVICE"
    assert report["program_readiness"] == "NOT_ASSESSED"
    assert report["live_eligible"] is report["forward_promotion_eligible"] is False
    assert report["orders_submitted"] == report["qualified_forward_sessions"] == 0
    if legacy:
        assert report["source_schema_version"] == "1.0"
    assert (tmp_path / "status.json").read_bytes() == original
    assert not list(tmp_path.rglob("*.db"))
