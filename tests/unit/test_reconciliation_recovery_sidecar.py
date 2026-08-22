from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/reconciliation_recovery_sidecar.py"
_spec = importlib.util.spec_from_file_location("reconciliation_recovery_sidecar", _SCRIPT)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
build_report = _module.build_report


def test_valid_recovery_output_is_preserved() -> None:
    raw = json.dumps(
        {
            "status": "RECOVERED",
            "halt_present_after": False,
            "reconciliation_state": "OK",
            "evidence_quality": "VALID",
            "halt_cleared": True,
            "orders_submitted": 0,
            "reasons": [],
        }
    )
    report = build_report(raw, remote_exit=0, run_id="123", commit="a" * 40)
    assert report["status"] == "RECOVERED"
    assert report["halt_present_after"] is False
    assert report["orders_submitted"] == 0


def test_invalid_or_failed_remote_output_is_fail_closed() -> None:
    invalid = build_report("not-json", remote_exit=255, run_id="123", commit="a" * 40)
    misleading = build_report(
        json.dumps(
            {
                "status": "CLEAR",
                "halt_present_after": False,
                "reconciliation_state": "OK",
                "evidence_quality": "VALID",
                "halt_cleared": False,
                "orders_submitted": 0,
            }
        ),
        remote_exit=1,
        run_id="123",
        commit="a" * 40,
    )
    assert invalid["status"] == "INCONCLUSIVE"
    assert invalid["halt_present_after"] is True
    assert misleading["status"] == "INCONCLUSIVE"
    assert misleading["halt_present_after"] is True


def test_workflow_uses_only_fixed_remote_command_and_publishes_sidecar() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / ".github/workflows/reconciliation-halt-recovery.yml").read_text()
    assert '"KIS smoke (autonomous)"' in text
    assert '"reconciliation-halt-recovery"' in text
    assert "automation/reconciliation-halt-recovery-last-run" in text
    assert "report.json" in text
    assert "bash -c" not in text
    assert "auto-invest reconcile-recover" not in text
    assert "rebalance-once" not in text
    assert "--confirm-live" not in text
