"""Server issuer timer has a fixed public-source command and no broker credentials."""

import shutil
import subprocess
from pathlib import Path

import pytest

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
