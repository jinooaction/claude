import json
import os
import subprocess
import sys
from pathlib import Path


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
