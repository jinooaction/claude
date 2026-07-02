from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "operator_status_probe.py"
_spec = importlib.util.spec_from_file_location("operator_status_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_manifest_matches_contract(capsys) -> None:
    rc = probe_main(["--manifest"])

    assert rc == 0
    assert capsys.readouterr().out.strip().splitlines() == [
        "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
        "money-path\tautomation/money-path-last-run\tLAST_RUN.md",
        (
            "capital-path-readiness\t"
            "automation/capital-path-readiness-last-run\tcapital_path_readiness.json"
        ),
        "money-gate-alignment\tautomation/money-gate-alignment-last-run\tmoney_gate_alignment.json",
        (
            "autonomous-work-execution\t"
            "automation/autonomous-work-execution-last-run\tautonomous_work_execution.json"
        ),
        "released-work\tautomation/released-work-last-run\treleased_work.json",
    ]


def test_probe_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    (tmp_path / "pipeline-liveness.md").write_text(
        "## 결정 JSON\n\n```json\n{\"overall\":\"OK\",\"checks\":[]}\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "money-gate-alignment.md").write_text(
        json.dumps({"overall_status": "BLOCKED", "next_action_ko": "복구한다."}),
        encoding="utf-8",
    )
    json_out = tmp_path / "operator_status.json"
    summary_out = tmp_path / "LAST_RUN.md"

    rc = probe_main(
        [
            "--evidence-dir",
            str(tmp_path),
            "--json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-02T09:25:00Z",
            "--run-id",
            "123",
            "--commit",
            "abc123",
            "--dashboard-url",
            "https://example.test/status.html",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(json_out.read_text(encoding="utf-8"))
    assert printed == written
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    assert written["overall_status"] == "ACTION_REQUIRED"
    assert written["alert_decision"]["should_send"] is True
    assert "운영자 상태 보고" in summary_out.read_text(encoding="utf-8")
