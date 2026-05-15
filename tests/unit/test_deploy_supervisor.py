"""Tests for the Supervisor abstraction (T014)."""

from __future__ import annotations

from unittest.mock import patch

from auto_invest.deploy.supervisor import (
    DryRunSupervisor,
    SystemdSupervisor,
)


def test_dryrun_captures_intents():
    s = DryRunSupervisor()
    assert s.is_running() is True
    r = s.stop_worker()
    assert r.ok
    assert s.is_running() is False
    r = s.start_worker()
    assert r.ok
    assert s.is_running() is True
    assert s.intents == ["stop", "start"]


def test_systemd_invokes_systemctl_via_subprocess():
    s = SystemdSupervisor(unit="test.service")
    with patch("auto_invest.deploy.supervisor.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        result = s.stop_worker()
        run.assert_called_once_with(
            ["systemctl", "stop", "test.service"],
            capture_output=True, text=True, check=False,
        )
        assert result.ok


def test_systemd_returncode_nonzero_marks_failure():
    s = SystemdSupervisor(unit="test.service")
    with patch("auto_invest.deploy.supervisor.subprocess.run") as run:
        run.return_value.returncode = 5
        run.return_value.stdout = ""
        run.return_value.stderr = "unit not found"
        result = s.start_worker()
        assert result.ok is False
        assert "unit not found" in result.stderr


def test_systemd_missing_systemctl_returns_127():
    s = SystemdSupervisor()
    with patch(
        "auto_invest.deploy.supervisor.subprocess.run",
        side_effect=FileNotFoundError("systemctl"),
    ):
        result = s.stop_worker()
        assert result.ok is False
        assert result.returncode == 127


def test_systemd_is_running_parses_active():
    s = SystemdSupervisor(unit="t.service")
    with patch("auto_invest.deploy.supervisor.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "active\n"
        run.return_value.stderr = ""
        assert s.is_running() is True
        run.return_value.returncode = 3
        run.return_value.stdout = "inactive\n"
        assert s.is_running() is False
