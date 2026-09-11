"""Execute the server capture tail with a fake transport; never contact a host."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("smoke,recorder,capture,expected,calls", [
    (0, True, 0, 0, True), (0, True, 1, 2, True),
    (1, True, 0, 1, False), (0, False, 0, 0, False),
])
def test_server_capture_preserves_approved_checkout_and_failure_status(
    tmp_path, smoke, recorder, capture, expected, calls,
):
    checkout = tmp_path / "approved checkout"
    marker = checkout / "src/auto_invest/execution/intraday_account_history.py"
    marker.parent.mkdir(parents=True)
    if recorder:
        marker.touch()
    script = (ROOT / "deploy/kis-smoke-on-instance.sh").read_text()
    tail = script[script.index("# Account source capture"):]
    # Shadow sudo in this test process. Its argument vector is evidence that
    # the production tail chooses only the intended script and output path.
    stub = 'sudo() { printf "%s\\n" "$@" > "$CALLS"; return "$CAPTURE"; }\n'
    output = tmp_path / "calls"
    live = tmp_path / "live"
    env = dict(os.environ, SMOKE_REPO=str(checkout), LIVE_REPO=str(live),
               pytest_exit=str(smoke), CAPTURE=str(capture), CALLS=str(output),
               KIS_APP_KEY="test-key", KIS_APP_SECRET="test-secret", KIS_ACCOUNT_NO="test-account")
    result = subprocess.run(["bash", "-c", stub + tail], env=env, capture_output=True, text=True)
    assert result.returncode == expected
    assert output.exists() is calls
    if calls:
        args = output.read_text().splitlines()
        assert args[-3:] == [str(checkout / "scripts/intraday_balance_check.py"),
                             "--history-db", str(live / "data/account-source.db")]
        assert args[args.index("--project") + 1] == str(checkout)
        assert "test-secret" not in result.stdout + result.stderr
