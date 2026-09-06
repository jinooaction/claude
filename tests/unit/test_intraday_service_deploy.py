import re
import subprocess
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_diagnostic_unit_is_installed_scheduled_and_cannot_access_account_db():
    service = (ROOT / "deploy/auto-invest-intraday-paper.service").read_text()
    timer = (ROOT / "deploy/auto-invest-intraday-paper.timer").read_text()
    sync = (ROOT / "deploy/sync-units.sh").read_text()
    assert "intraday_runtime.py service\n" in service
    assert "Type=oneshot" in service and "StateDirectoryMode=0700" in service
    assert "InaccessiblePaths=-/opt/auto-invest/data/auto_invest.db" in service
    assert "OnUnitActiveSec=60" in timer
    assert "OnUnitInactiveSec=60" in timer
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


def test_workflow_accepts_real_status_protocol_and_rejects_wrong_source(tmp_path):
    import json

    from auto_invest.analytics.intraday_service import (
        publish,
        read_service_status,
        service_identity,
    )

    workflow = (ROOT / ".github/workflows/intraday-paper-status.yml").read_text()
    program = textwrap.dedent(
        workflow.split("python3 - <<'PY'\n", 1)[1].split("          PY", 1)[0]
    )
    report = tmp_path / "report.txt"
    program = program.replace("/tmp/intraday-status.txt", str(report))
    sources = [
        ROOT / "scripts/intraday_runtime.py",
        ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json",
        ROOT / "src/auto_invest/analytics/intraday_runtime.py",
        ROOT / "src/auto_invest/analytics/intraday_service.py",
        ROOT / "src/auto_invest/analytics/intraday_paper_challenger.py",
        ROOT / "src/auto_invest/market_data/intraday.py",
    ]
    now = datetime.now(UTC)
    publish(tmp_path, dict(status="WAIT_SESSION", identity=service_identity(sources)), now)
    status = read_service_status(tmp_path, now)
    report.write_text("INTRADAY_TIMER=active\n" + json.dumps(status))
    exec(compile(program, "workflow-status", "exec"), {})
    status["identity"] = "0" * 64
    report.write_text("INTRADAY_TIMER=active\n" + json.dumps(status))
    with pytest.raises(AssertionError, match="service code differs"):
        exec(compile(program, "workflow-status", "exec"), {})
