import json
import os
import subprocess
import sys


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
