"""Server issuer timer has a fixed public-source command and no broker credentials."""

import importlib.util
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from auto_invest.analytics.filing_observations import ISSUER_CIK, ISSUER_FEED, Observation, RunStore

ROOT = Path(__file__).resolve().parents[2]


def test_issuer_service_isolated_and_timer_is_calendar_based():
    service = (ROOT / "deploy/auto-invest-issuer-observations.service").read_text()
    timer = (ROOT / "deploy/auto-invest-issuer-observations.timer").read_text()
    helper = (ROOT / "deploy/issuer-observations-on-instance.sh").read_text()
    sync = (ROOT / "deploy/sync-units.sh").read_text()
    gateway = (ROOT / "deploy/repair-ssh-boundary.sh").read_text()
    observe = (ROOT / "deploy/observe-on-instance.sh").read_text()
    backup = (ROOT / ".github/workflows/server-issuer-observations-backup.yml").read_text()

    assert "EnvironmentFile=" not in service
    assert "InaccessiblePaths=-/opt/auto-invest/.env -/opt/auto-invest/data" in service
    assert "ReadWritePaths=/var/lib/auto-invest-issuer-observations" in service
    assert "collect-issuer-server --help" in service
    assert "OnCalendar=*-*-* *:00/15:00" in timer
    assert "Persistent=true" in timer
    assert "--mode capacity" in helper
    assert "--config deploy/issuer-filings.json" in helper
    assert "server-${INVOCATION_ID}" in helper
    assert ".env" not in helper and "KIS" not in helper
    assert "enable --now auto-invest-issuer-observations.timer" in sync
    assert r"observe\ issuer-status)" in gateway
    assert r"observe\ issuer-store-export)" in gateway
    assert r"observe\ issuer-store-export\ *)" not in gateway
    assert "issuer-store-export takes no args" in observe
    assert "flock -s -w 190 9" in observe
    assert "filing_server_snapshot.py inspect-store" in observe
    assert "tar -C \"${store}\" -czf -" in observe
    assert "observe issuer-store-export" in backup
    assert "automation/server-issuer-observations" in backup
    assert "filing_server_snapshot.py unpack" in backup
    assert "filing_publication.py --mode pack-delta" in backup
    assert "filing_publication.py --mode apply-delta" in backup
    assert "retention-days: 90" in backup
    assert "SEC_USER_AGENT" not in backup and "KIS_" not in backup


def test_systemd_accepts_issuer_calendar_when_available():
    binary = shutil.which("systemd-analyze")
    if binary is None:
        pytest.skip("systemd-analyze is available on the Linux CI runner")
    result = subprocess.run([binary, "calendar", "*-*-* *:00/15:00"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_status_keeps_missed_slots_after_observer_resumes(tmp_path):
    script = ROOT / "scripts/filing_observations.py"
    spec = importlib.util.spec_from_file_location("issuer_timer_status", script)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    stamps = iter(["2026-10-01T00:00:05Z", "2026-10-01T00:45:05Z"])
    store = RunStore(tmp_path, clock=lambda: next(stamps))
    digest = store.blobs.put(b"issuer listing")

    def publish(index, started, parent):
        run_id = "server-" + str(index) * 32
        second = started.replace(":01Z", ":02Z")
        receipt = Observation(
            f"84dc0271-07f0-41ea-856b-510002131b8{index}", ISSUER_CIK, None,
            "issuer_listing", ISSUER_FEED, digest, started, second, second, {},
        )
        manifest = {
            "schema_version": 1, "run_id": run_id, "source_commit": "a" * 40,
            "config_sha256": "b" * 64, "started_at": started, "ended_at": second,
            "previous_run_sha256": parent, "observations": [], "failures": [],
            "coverage": {"succeeded": 1, "failed": 0, "skipped": 0},
            "selection": {"unselected": 0, "limit_skipped": 0},
            "circuit": {"consecutive_failures": 0, "cooldown_until": None},
        }
        return store.publish(manifest, [receipt])

    first = publish(1, "2026-10-01T00:00:01Z", None)
    publish(2, "2026-10-01T00:45:01Z", first)
    status = cli.server_status(store, datetime(2026, 10, 1, 1, 15, tzinfo=UTC))
    by_time = {slot["scheduled_at"]: slot["state"] for slot in status["slots_24h"]}
    assert by_time["2026-10-01T00:00:00Z"] == "success"
    assert by_time["2026-10-01T00:15:00Z"] == "missing"
    assert by_time["2026-10-01T00:30:00Z"] == "missing"
    assert by_time["2026-10-01T00:45:00Z"] == "success"
