import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from auto_invest.execution import intraday_selftest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_installed_engine_checks_work_with_all_network_connections_forbidden(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("self-test attempted a socket connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setenv("KIS_APP_SECRET", "must-not-be-used")
    result = await intraday_selftest.self_test()
    assert result == dict(
        status="SELF_TEST_PASSED", mode="OFFLINE_SELF_TEST",
        checks=["PARTIAL_FILL_AND_CANCELLATION", "PERSISTENT_STOP_AND_RESTART"],
        live_eligible=False, orders_submitted=0,
    )


@pytest.mark.asyncio
async def test_private_failure_is_reported_as_a_failed_check(monkeypatch):
    async def fail(**kwargs):
        raise RuntimeError("private broker credential")

    monkeypatch.setattr(intraday_selftest, "rehearse", fail)
    result = await intraday_selftest.self_test()
    assert result["status"] == "FAILED"
    assert result["failed_check"] == "PARTIAL_FILL_AND_CANCELLATION"
    assert "private" not in json.dumps(result)


@pytest.mark.asyncio
async def test_incorrect_recovery_result_is_not_a_success(monkeypatch):
    async def incorrect(*args, **kwargs):
        return {"phase": "STOPPED"}

    monkeypatch.setattr(intraday_selftest, "run", incorrect)
    result = await intraday_selftest.self_test()
    assert result["status"] == "FAILED"
    assert result["failed_check"] == "PERSISTENT_STOP_AND_RESTART"


def test_operator_self_test_is_executable_without_keys_or_a_user_database(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("KIS_", "APCA_"))}
    result = subprocess.run(
        [sys.executable, "scripts/intraday_operator.py", "self-test"],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "SELF_TEST_PASSED"
    production = tmp_path / "production.db"
    production.write_bytes(b"existing user data")
    denied = subprocess.run(
        [sys.executable, "scripts/intraday_operator.py", "self-test", "--db", str(production)],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=30,
    )
    assert denied.returncode == 2
    assert production.read_bytes() == b"existing user data"
