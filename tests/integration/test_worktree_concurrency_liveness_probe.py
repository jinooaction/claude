"""스펙 109 - worktree 동시 작업 생존성 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.worktree_concurrency_liveness import (
    COMPLETED_CANDIDATE_ID,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
)

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "worktree_concurrency_liveness_probe.py"
_spec = importlib.util.spec_from_file_location(
    "worktree_concurrency_liveness_probe",
    _PROBE_PATH,
)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    guard_check = tmp_path / "guard_check.txt"
    guard_check.write_text(
        "# local multi-session guard\nfindings:\n  - OK: 동시 세션 충돌 징후 없음.\n",
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
            "--guard-check",
            str(guard_check),
            "--released-work",
            str(released_work),
            "--format",
            "json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-10T08:00:00Z",
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
    assert written["guard_behavior_summary"]["conflict_pre_push"]["actual"] == "BLOCK"
    assert written["runtime_state_summary"]["state"] == "PASS"
    assert "worktree 동시 작업 생존성 계약" in summary_out.read_text(encoding="utf-8")
