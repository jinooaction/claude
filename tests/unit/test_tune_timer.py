"""Tests for the autonomous-tuner systemd artifacts (spec 005 followup).

These validate the deploy wiring that runs `auto-invest tune --apply`
off-hours: the wrapper script, the oneshot service, and the daily timer.
The tuner's runtime safety (L1-only, market-hours gate, min-sample gate,
idempotency, kernel refusal) is covered by the spec 005 tuner tests; here
we only assert that the scheduling artifacts invoke that vetted CLI and
fire strictly OUTSIDE the US regular session.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "deploy"

# US regular session in UTC is 13:30-20:00. Off-hours tuning must avoid
# hours 13..20 inclusive (matches the deploy timer's calendar rationale).
US_REGULAR_HOURS_UTC = set(range(13, 21))


def _read(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def test_artifacts_exist():
    assert (DEPLOY / "run-tune.sh").is_file()
    assert (DEPLOY / "auto-invest-tune.service").is_file()
    assert (DEPLOY / "auto-invest-tune.timer").is_file()


def test_wrapper_invokes_vetted_tune_cli_with_apply():
    body = _read("run-tune.sh")
    assert "auto-invest tune --apply" in body
    assert "--db" in body
    assert "--output-root" in body


def test_wrapper_is_failsafe_when_db_missing():
    """No telemetry DB yet (fresh instance) must exit 0, not fail red."""
    body = _read("run-tune.sh")
    # Guards on a missing DB file and exits cleanly before calling the CLI.
    assert 'if [[ ! -f "$db" ]]' in body
    assert "exit 0" in body


def test_wrapper_is_executable():
    mode = (DEPLOY / "run-tune.sh").stat().st_mode
    assert mode & 0o111, "run-tune.sh must be executable (like run-worker.sh)"


def test_service_is_oneshot_running_the_wrapper():
    body = _read("auto-invest-tune.service")
    assert "Type=oneshot" in body
    assert "User=auto-invest" in body
    assert "ExecStart=/opt/auto-invest/deploy/run-tune.sh" in body


def test_timer_fires_daily_off_hours_and_is_persistent():
    body = _read("auto-invest-tune.timer")
    m = re.search(r"^OnCalendar=.*\s(\d{1,2}):\d{2}:\d{2}\s*$", body, re.MULTILINE)
    assert m, "timer must declare an OnCalendar with an explicit HH:MM:SS"
    hour = int(m.group(1))
    assert hour not in US_REGULAR_HOURS_UTC, (
        f"tuner must fire outside US regular hours (UTC), got {hour}:00"
    )
    # Strictly after the latest possible US close (21:00 UTC under EST).
    assert hour >= 22, f"tuner should fire after the US close, got {hour}:00"
    assert "Persistent=true" in body
    assert "Unit=auto-invest-tune.service" in body


def test_timer_requires_its_service():
    body = _read("auto-invest-tune.timer")
    assert "Requires=auto-invest-tune.service" in body


def test_cloud_init_installs_and_enables_the_tune_timer():
    body = _read("vultr-userdata.sh")
    assert "auto-invest-tune.service" in body
    assert "auto-invest-tune.timer" in body
    assert "systemctl enable --now auto-invest-tune.timer" in body
