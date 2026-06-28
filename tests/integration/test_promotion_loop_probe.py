"""스펙 068 — 자율 승격 루프 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _REPO_ROOT / "scripts" / "promotion_loop_probe.py"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "promotion_loop" / "fresh"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "autonomous-promotion-loop.yml"

_spec = importlib.util.spec_from_file_location("promotion_loop_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_json_output_includes_expected_sections(capsys) -> None:
    rc = probe_main(
        [
            "--evidence-dir",
            str(_FIXTURES),
            "--json",
            "--now",
            "2026-06-29T02:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "test-run"
    assert payload["assessments"]
    assert payload["assessments"][0]["stage"]


def test_probe_writes_sidecar_artifacts(tmp_path, capsys) -> None:
    summary = tmp_path / "LAST_RUN.md"
    summary_json = tmp_path / "promotion_summary.json"
    queue = tmp_path / "promotion_queue.json"
    rc = probe_main(
        [
            "--evidence-dir",
            str(_FIXTURES),
            "--summary-out",
            str(summary),
            "--json-out",
            str(summary_json),
            "--queue-out",
            str(queue),
            "--now",
            "2026-06-29T02:00:00Z",
            "--commit",
            "abc1234",
        ]
    )
    assert rc == 0
    assert "자율 승격 루프" in summary.read_text(encoding="utf-8")
    assert json.loads(summary_json.read_text(encoding="utf-8"))["assessments"]
    assert json.loads(queue.read_text(encoding="utf-8"))["queue"]
    assert "읽기 전용 실행입니다" in capsys.readouterr().out


def test_autonomous_promotion_workflow_is_read_only_and_publishes_sidecar() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text and "workflow_dispatch:" in text
    assert "automation/autonomous-promotion-last-run" in text
    assert "promotion_loop_probe.py" in text
    assert "promotion_queue.json" in text
    assert "VULTR_SSH" not in text
    assert "KIS_" not in text
    assert "ssh " not in text and "ssh -" not in text
    assert "no orders, no capital change, no whitelist/caps change, no live strategy change" in text
