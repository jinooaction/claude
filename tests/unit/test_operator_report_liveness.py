"""스펙 118 - 운영자 이해 가능 보고 생존성 계약 단위 테스트."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.operator_report_liveness import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_operator_report_liveness_report,
)

NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
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


def _final_report_ok() -> str:
    return "\n".join(
        [
            "운영자가 바로 이해할 수 있게 완료 보고의 의미 검사가 main에 들어갔다.",
            "",
            "무엇을 고쳤는가: 최종 보고가 실제 운영 상태 변화와 검증, "
            "남은 위험을 담는지 읽기 전용으로 검사한다.",
            "돈 경로와 안전 경계: 주문, 자본, whitelist/caps, 비밀값은 "
            "건드리지 않았다. 다음 세션은 released-work가 이 후보를 소비하면 "
            "같은 작업을 반복하지 않는다.",
            "검증: focused pytest, 전체 pytest, ruff, handoff 사실 검증, "
            "strict harness로 확인한다.",
            "남은 위험: 실제 서버와 KIS 계좌 상태는 이 보고서의 범위 밖이다.",
            "증거: PR #525, 커밋 abc123, sidecar run 123은 위 결론을 뒷받침하는 증거다.",
        ]
    )


def _final_report_evidence_only() -> str:
    return "\n".join(
        [
            "PR #525 머지함.",
            "커밋 abc123.",
            "uv run pytest 통과.",
            "ruff 통과.",
        ]
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence = {
        "final-report": _final_report_ok(),
        "released-work": _released(COMPLETED_CANDIDATE_ID),
    }
    evidence.update(overrides)
    return evidence


def test_all_evidence_passes_contract_ready():
    report = build_operator_report_liveness_report(
        _evidence(),
        repo_root=REPO,
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.run_id == "123"
    assert report.commit == "abc123"
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert report.final_report_summary["state"] == GATE_PASS
    assert report.rule_surface_summary["quality_006"]["status"] == GATE_PASS
    assert {gate.status for gate in report.quality_gates} == {GATE_PASS}
    assert "no broker API call" in report.safety_invariants
    assert "운영자 이해 가능 보고 생존성 계약" in report.as_markdown()


def test_missing_final_report_waits_instead_of_failing():
    report = build_operator_report_liveness_report(
        _evidence(**{"final-report": None}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["final_report_observation"].status == GATE_WAIT


def test_evidence_only_final_report_blocks_contract():
    report = build_operator_report_liveness_report(
        _evidence(**{"final-report": _final_report_evidence_only()}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["final_report_observation"].status == GATE_FAIL
    assert report.final_report_summary["evidence_only"] is True


def test_malformed_released_work_blocks_contract():
    report = build_operator_report_liveness_report(
        _evidence(**{"released-work": "{not json"}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["released_work_completion"].status == GATE_FAIL


def test_missing_released_work_waits_for_sidecar():
    report = build_operator_report_liveness_report(
        _evidence(**{"released-work": None}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["released_work_completion"].status == GATE_WAIT


def test_broken_quality_006_blocks_contract(tmp_path):
    repo = _minimal_repo(tmp_path)
    (repo / ".codex/harness/quality_tasks.toml").write_text(
        """
[[tasks]]
id = "QUALITY-006"
title = "운영자가 완료 보고를 이해하지 못함"
prompt = "그래서 뭘 했다는거야?"
required_categories = ["operator_readability"]
success_criteria = ["쉽게 설명한다"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    report = build_operator_report_liveness_report(
        _evidence(),
        repo_root=repo,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["rule_surface_liveness"].status == GATE_FAIL


def _minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    copies = [
        "AGENTS.md",
        "HANDOFF.md",
        ".codex/quality-gate.md",
        ".github/pull_request_template.md",
        ".codex/harness/quality_tasks.toml",
    ]
    for rel in copies:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, target)
    return repo
