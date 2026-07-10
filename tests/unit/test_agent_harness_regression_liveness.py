"""스펙 110 - agent harness 회귀 생존성 계약 단위 테스트."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.agent_harness_regression_liveness import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_agent_harness_regression_liveness_report,
)

NOW = datetime(2026, 7, 10, 9, 0, 0, tzinfo=UTC)
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


def _strict_ok() -> str:
    return (
        "에이전트 하네스 평가\n"
        "종합 판정: OK (14/14)\n"
        "\n"
        "통제 항목:\n"
        "- PASS evaluation_task_suite: ok\n"
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence = {
        "strict-output": _strict_ok(),
        "released-work": _released(COMPLETED_CANDIDATE_ID),
    }
    evidence.update(overrides)
    return evidence


def test_all_evidence_passes_contract_ready():
    report = build_agent_harness_regression_liveness_report(
        _evidence(),
        repo_root=REPO,
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert report.strict_observation_summary["state"] == GATE_PASS
    assert report.harness_suite_summary["task_suite"]["status"] == GATE_PASS
    assert report.harness_suite_summary["quality_suite"]["status"] == GATE_PASS
    assert report.harness_suite_summary["redteam_suite"]["status"] == GATE_PASS
    assert {gate.status for gate in report.quality_gates} == {GATE_PASS}
    assert "no broker API call" in report.safety_invariants
    assert "agent harness 회귀 생존성 계약" in report.as_markdown()


def test_missing_strict_output_waits_instead_of_failing():
    report = build_agent_harness_regression_liveness_report(
        _evidence(**{"strict-output": None}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["strict_harness_observation"].status == GATE_WAIT


def test_degraded_strict_output_blocks_contract():
    report = build_agent_harness_regression_liveness_report(
        _evidence(**{"strict-output": "에이전트 하네스 평가\n종합 판정: DEGRADED (13/14)\n"}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["strict_harness_observation"].status == GATE_FAIL


def test_malformed_released_work_blocks_contract():
    report = build_agent_harness_regression_liveness_report(
        _evidence(**{"released-work": "{not json"}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["released_work_completion"].status == GATE_FAIL


def test_missing_released_work_waits_for_sidecar():
    report = build_agent_harness_regression_liveness_report(
        _evidence(**{"released-work": None}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["released_work_completion"].status == GATE_WAIT


def test_broken_quality_suite_blocks_contract(tmp_path):
    repo = _minimal_repo(tmp_path)
    (repo / ".codex/harness/quality_tasks.toml").write_text(
        """
[[tasks]]
id = "QUALITY-001"
title = "불완전한 품질 과제"
prompt = "범주가 부족하다."
required_categories = ["problem_definition"]
success_criteria = ["하나만 있다"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    report = build_agent_harness_regression_liveness_report(
        _evidence(),
        repo_root=repo,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["harness_suite_coverage"].status == GATE_FAIL
    assert report.harness_suite_summary["quality_suite"]["status"] == GATE_FAIL


def test_missing_agent_harness_source_blocks_contract(tmp_path):
    repo = _minimal_repo(tmp_path)
    (repo / "scripts/agent_harness_probe.py").unlink()

    report = build_agent_harness_regression_liveness_report(
        _evidence(),
        repo_root=repo,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["static_harness_surfaces"].status == GATE_FAIL


def _minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    copies = [
        "scripts/agent_harness_probe.py",
        "scripts/check_handoff_facts.py",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        ".codex/quality-gate.md",
        ".github/pull_request_template.md",
        ".github/workflows/pr-quality-gate.yml",
        "AGENTS.md",
        "HANDOFF.md",
    ]
    for rel in copies:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, target)
    return repo
