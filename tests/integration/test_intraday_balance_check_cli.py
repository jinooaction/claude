import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_balance_check_without_credentials_does_not_create_a_token_or_claim_success(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/intraday_balance_check.py"
    env = {key: value for key, value in os.environ.items() if not key.startswith("KIS_")}
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout) == dict(
        status="DATA_ACCESS_REQUIRED", orders_submitted=0, live_eligible=False
    )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [
    ["--transactions-from", "20260901"],
    ["--transactions-from", "20260230", "--transactions-through", "20260910"],
    ["--transactions-from", "20260910", "--transactions-through", "20260901"],
])
def test_invalid_transaction_window_fails_before_authentication(tmp_path, args):
    script = Path(__file__).resolve().parents[2] / "scripts/intraday_balance_check.py"
    env = {key: value for key, value in os.environ.items() if not key.startswith("KIS_")}
    result = subprocess.run([sys.executable, str(script), *args], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"].startswith("TRANSACTIONS_")
    assert not list(tmp_path.iterdir())


def test_missing_execution_database_is_rejected_before_authentication(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/intraday_balance_check.py"
    path = tmp_path / "missing.db"
    env = {key: value for key, value in os.environ.items() if not key.startswith("KIS_")}
    result = subprocess.run([
        sys.executable, str(script), "--transactions-from", "20260910",
        "--transactions-through", "20260910", "--execution-db", str(path),
    ], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "COST_LEDGER_UNAVAILABLE"
    assert not path.exists()
