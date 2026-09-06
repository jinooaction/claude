import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_diagnostic_unit_is_installed_scheduled_and_cannot_access_account_db():
    service = (ROOT / "deploy/auto-invest-intraday-paper.service").read_text()
    timer = (ROOT / "deploy/auto-invest-intraday-paper.timer").read_text()
    sync = (ROOT / "deploy/sync-units.sh").read_text()
    assert "intraday_runtime.py service\n" in service
    assert "Type=oneshot" in service and "StateDirectoryMode=0700" in service
    assert "InaccessiblePaths=-/opt/auto-invest/data/auto_invest.db" in service
    assert "OnUnitActiveSec=60" in timer
    assert "enable --now auto-invest-intraday-paper.timer" in sync
    assert "auto-invest-intraday-paper.service" in sync
    assert "--confirm-live" not in service


def test_fixed_observer_gateway_rejects_arguments_and_shell_injection(tmp_path):
    source = (ROOT / "deploy/repair-ssh-boundary.sh").read_text()
    gateway = source.split("<<'EOF_GATEWAY'\n", 1)[1].split("\nEOF_GATEWAY", 1)[0]
    path = tmp_path / "gateway.sh"
    path.write_text(gateway)
    for command in ("observe intraday-paper-status extra", "observe intraday-paper-status; id"):
        result = subprocess.run(
            ["bash", str(path)],
            env={"SSH_ORIGINAL_COMMAND": command, "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 126
    assert re.search(r"observe\\ intraday-paper-status\)", gateway)
    helper = (ROOT / "deploy/observe-on-instance.sh").read_text()
    body = helper.split("intraday-paper-status)", 1)[1].split(";;", 1)[0]
    assert '"$#" -eq 0' in body
    assert "service-status" in body
    assert "systemctl start" not in body and "enable" not in body
