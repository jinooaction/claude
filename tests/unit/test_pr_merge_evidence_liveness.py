"""스펙 108 - PR/머지 증거 생존성 계약 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.pr_merge_evidence_liveness import (
    BLOCKED,
    COMPLETED_CANDIDATE_ID,
    CONTRACT_READY,
    GATE_FAIL,
    GATE_PASS,
    GATE_WAIT,
    NEXT_AUTONOMOUS_CANDIDATE_ID,
    OBSERVATION_WAIT,
    build_pr_merge_evidence_liveness_report,
)

NOW = datetime(2026, 7, 10, 6, 0, 0, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]


def _valid_pr_body() -> str:
    risk_grade_lines = [
        "- [ ] 등급 0: 설명, 조사, 단순 문서 오탈자처럼 실행 동작이 바뀌지 않음",
        "- [ ] 등급 1: 일반 코드나 테스트 변경. 안전 경계, 배포, "
        "돈 경로, 자동화 흐름은 바꾸지 않음",
        "- [x] 등급 2: 운영 체계 변경. 훅, 설정, 워크플로, "
        "`AGENTS.md`, `CLAUDE.md`, `HANDOFF.md`, 스킬, 인계, 머지 흐름을 바꿈",
        "- [ ] 등급 3: 안전 경계 변경. 헌법, 커널 목록, 위험 게이트, "
        "주문 제한, 감사 로그, 비밀값, 배포 제한, 외부 API 안전장치를 바꿈",
        "- [ ] 등급 4: 돈 경로 변경. 실제 주문, 실거래 전환, 자본 배분, "
        "계좌 노출, 라이브 전략 교체, 운영자 비용 발생 가능성이 있음",
    ]
    return f"""# 변경 요약

- PR/머지 증거 생존성 계약 추가.

## 위험 등급

{chr(10).join(risk_grade_lines)}

## 문제 정의

- 요청: 다음 자율 후보를 완료한다.
- 실제 목표: PR/머지 증거 생존성을 재현 가능하게 만든다.
- 비목표: 돈 경로 변경 없음.
- 위험: 완료 증거 누락.
- 완료 기준: 테스트와 하네스 통과.

## 탐색 근거

- 읽은 파일: HANDOFF.md, PR 템플릿.
- 확인한 실행 경로: probe.
- 제거하거나 줄인 기능: 없음.
- 남긴 기능 또는 대체 수단: 기존 PR 품질 관문.

## 변경 내용

- 읽기 전용 보고서 추가.

## 검증

- [x] `uv run pytest`
- [x] `uv run ruff check src tests`
- [x] 문서·설정 변경에 맞는 형식 검증: `git diff --check`
- [x] 등급 2 이상 실제 적용 경로 확인: focused probe

## 하네스 검증

- 하네스 평가: `uv run python scripts/agent_harness_probe.py --strict` OK.
- HANDOFF 검증: `uv run python scripts/check_handoff_facts.py` OK.

## 안전 경계

- Kernel 터치: 없음
- 안전 경계 변경: 없음
- 돈 경로 변경: 없음
- 감사 로그·비밀값·주문 제한 영향: 없음

## 인계

- 다음 세션이 알아야 할 상태: 보고서가 완료 증거를 분리한다.
- 남은 위험: post-merge deploy 관측 대기 가능.
- 실행하지 못한 검증: 없음

## 자동 머지 준비

- [x] 작업 완료
- [x] 테스트 통과
- [x] 린트 깨끗함
- [x] PR 머지 가능 상태 확인
- [x] `WIP` 또는 `DO NOT MERGE` 표식 없음
- [x] Kernel 터치 커밋 해시를 본문에 명시함, 또는 Kernel 터치 없음
"""


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


def _success_deploy() -> str:
    return (
        "대상 main 커밋: abc123 Merge pull request #501 from branch\n"
        "Deploy on merge to main: success\n"
        "KIS smoke sidecar: success\n"
        "서버 audit_log는 운영자 전용 표면이다.\n"
    )


def _evidence(**overrides: str | None) -> dict[str, str | None]:
    evidence = {
        "pr-body": _valid_pr_body(),
        "released-work": _released(COMPLETED_CANDIDATE_ID),
        "deploy-status": _success_deploy(),
    }
    evidence.update(overrides)
    return evidence


def _patch_merge(monkeypatch, subject: str = "Merge pull request #501 from branch") -> None:
    import auto_invest.analytics.pr_merge_evidence_liveness as module

    monkeypatch.setattr(
        module,
        "_git",
        lambda _repo, *_args: f"abc123456789\tabc1234\t{subject}",
    )


def test_all_evidence_passes_contract_ready(monkeypatch):
    _patch_merge(monkeypatch)
    report = build_pr_merge_evidence_liveness_report(
        _evidence(),
        repo_root=REPO,
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == CONTRACT_READY
    assert report.completed_candidate_id == COMPLETED_CANDIDATE_ID
    assert report.next_candidate_id == NEXT_AUTONOMOUS_CANDIDATE_ID
    assert report.merge_summary["pr_number"] == 501
    assert report.deploy_summary["state"] == GATE_PASS
    assert {gate.status for gate in report.quality_gates} == {GATE_PASS}
    assert "no orders" in report.safety_invariants
    assert "PR/머지 증거 생존성 계약" in report.as_markdown()


def test_missing_pr_body_waits_instead_of_failing(monkeypatch):
    _patch_merge(monkeypatch)
    report = build_pr_merge_evidence_liveness_report(
        _evidence(**{"pr-body": None}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["pr_body_quality"].status == GATE_WAIT


def test_invalid_pr_body_blocks_contract(monkeypatch):
    _patch_merge(monkeypatch)
    body = _valid_pr_body().replace("agent_harness_probe.py --strict", "agent harness")
    report = build_pr_merge_evidence_liveness_report(
        _evidence(**{"pr-body": body}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["pr_body_quality"].status == GATE_FAIL


def test_malformed_released_work_blocks_contract(monkeypatch):
    _patch_merge(monkeypatch)
    report = build_pr_merge_evidence_liveness_report(
        _evidence(**{"released-work": "{not json"}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["released_work_completion"].status == GATE_FAIL


def test_missing_deploy_observation_waits(monkeypatch):
    _patch_merge(monkeypatch)
    report = build_pr_merge_evidence_liveness_report(
        _evidence(**{"deploy-status": None}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == OBSERVATION_WAIT
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["deploy_status_observation"].status == GATE_WAIT


def test_failed_deploy_observation_blocks(monkeypatch):
    _patch_merge(monkeypatch)
    report = build_pr_merge_evidence_liveness_report(
        _evidence(**{"deploy-status": "Deploy on merge to main: failed, rollback"}),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["deploy_status_observation"].status == GATE_FAIL


def test_non_pr_main_commit_blocks(monkeypatch):
    _patch_merge(monkeypatch, "docs: refresh handoff")
    report = build_pr_merge_evidence_liveness_report(
        _evidence(),
        repo_root=REPO,
        now=NOW,
    )

    assert report.overall_status == BLOCKED
    gates = {gate.gate_id: gate for gate in report.quality_gates}
    assert gates["main_merge_evidence"].status == GATE_FAIL
