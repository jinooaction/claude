"""스펙 110 - agent harness 회귀 생존성 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.agent_harness_regression_liveness import (
    COMPLETED_CANDIDATE_ID,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
)

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "agent_harness_regression_liveness_probe.py"
_spec = importlib.util.spec_from_file_location(
    "agent_harness_regression_liveness_probe",
    _PROBE_PATH,
)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    strict_output = tmp_path / "strict-output.txt"
    strict_output.write_text(
        "에이전트 하네스 평가\n종합 판정: OK (14/14)\n",
        encoding="utf-8",
    )
    released_work = tmp_path / "released_work.json"
    released_work.write_text(
        json.dumps(
            {
                "released_work": [
                    {"candidate_id": COMPLETED_CANDIDATE_ID, "status": "released"}
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    json_out = tmp_path / "report.json"
    summary_out = tmp_path / "report.md"

    rc = probe_main(
        [
            "--repo-root",
            str(_ROOT),
            "--strict-output",
            str(strict_output),
            "--released-work",
            str(released_work),
            "--format",
            "json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-10T09:00:00Z",
            "--run-id",
            "123",
            "--commit",
            "abc123",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(json_out.read_text(encoding="utf-8"))
    assert printed == written
    assert written["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert written["next_candidate_id"] == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert written["strict_observation_summary"]["state"] == "PASS"
    assert written["harness_suite_summary"]["redteam_suite"]["status"] == "PASS"
    assert "agent harness 회귀 생존성 계약" in summary_out.read_text(encoding="utf-8")
