"""스펙 109 - worktree 동시 작업 생존성 계약 단위 테스트."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.worktree_concurrency_liveness import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_worktree_concurrency_liveness_report,
)

NOW = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]


def _released(*candidate_ids: str) -> str:
    return json.dumps(
        {
            "released_work": [
                {"candidate_id": candidate_id, "status": "released"}
                for candidate_id in candidate_ids
            ]
        },
        ensure_ascii=False,
    )


def _guard_check(level: str = "WARN") -> str:
    return (
        "# local multi-session guard\n"
        "current thread : CODEX_THREAD_ID:this\n"
        "findings:\n"
        f"  - {level}: synthetic observation\n"
        "required action:\n"
        "  - `python3 scripts/local_concurrency_guard.py --mode isolate`를 실행하세요.\n"
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence = {
        "guard-check": _guard_check(),
        "released-work": _released(COMPLETED_CANDIDATE_ID),
    }
    evidence.update(overrides)
    return evidence


def test_all_evidence_passes_contract_ready():
    report = build_worktree_concurrency_liveness_report(
        _evidence(),
        repo_root=REPO,
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert report.runtime_state_summary["state"] == GATE_PASS
    assert {gate.status for gate in report.quality_gates} == {GATE_PASS}
    assert report.guard_behavior_summary["conflict_check"]["actual"] == "WARN"
    assert report.guard_behavior_summary["conflict_pre_commit"]["actual"] == "BLOCK"
    assert "no worktree creation" in report.safety_invariants
    assert "worktree 동시 작업 생존성 계약" in report.as_markdown()


def test_missing_runtime_guard_output_waits_instead_of_failing():
    report = build_worktree_concurrency_liveness_report(
        _evidence(**{"guard-check": None}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["runtime_guard_observation"].status == GATE_WAIT


def test_malformed_released_work_blocks_contract():
    report = build_worktree_concurrency_liveness_report(
        _evidence(**{"released-work": "{not json"}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["released_work_completion"].status == GATE_FAIL


def test_missing_pre_commit_hook_blocks_contract(tmp_path):
    repo = _minimal_repo(tmp_path)
    (repo / ".githooks/pre-commit").unlink()

    report = build_worktree_concurrency_liveness_report(
        _evidence(),
        repo_root=repo,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["static_operating_surfaces"].status == GATE_FAIL
    assert gates["git_hook_blocking_registration"].status == GATE_FAIL


def test_session_start_guard_after_ground_truth_blocks_contract(tmp_path):
    repo = _minimal_repo(tmp_path)
    (repo / ".codex/hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 .codex/hooks/git_ground_truth.py",
                                },
                                {
                                    "type": "command",
                                    "command": (
                                        "python3 scripts/local_concurrency_guard.py "
                                        "--mode session-start"
                                    ),
                                },
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    report = build_worktree_concurrency_liveness_report(
        _evidence(),
        repo_root=repo,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["session_start_guard_registration"].status == GATE_FAIL


def test_guard_failure_output_blocks_contract():
    report = build_worktree_concurrency_liveness_report(
        _evidence(**{"guard-check": "local multi-session guard failed: boom"}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["runtime_guard_observation"].status == GATE_FAIL


def _minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    (repo / "scripts").mkdir()
    (repo / ".codex").mkdir()
    (repo / ".githooks").mkdir()
    shutil.copy2(REPO / "scripts/local_concurrency_guard.py", repo / "scripts")
    (repo / "scripts/agent_harness_probe.py").write_text("# stub\n", encoding="utf-8")
    (repo / ".codex/hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "python3 scripts/local_concurrency_guard.py "
                                        "--mode session-start"
                                    ),
                                },
                                {
                                    "type": "command",
                                    "command": "python3 .codex/hooks/git_ground_truth.py",
                                },
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    (repo / ".githooks/pre-commit").write_text(
        "#!/bin/sh\nexec python3 scripts/local_concurrency_guard.py --mode pre-commit\n",
        encoding="utf-8",
    )
    (repo / ".githooks/pre-push").write_text(
        "#!/bin/sh\nexec python3 scripts/local_concurrency_guard.py --mode pre-push\n",
        encoding="utf-8",
    )
    return repo
