from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "check_pr_quality_gate.py"


def _body(*, grade: int, harness: str) -> str:
    grade_rows = []
    for idx in range(5):
        mark = "x" if idx == grade else " "
        grade_rows.append(f"- [{mark}] 등급 {idx}: 설명")

    return f"""# 변경 요약

- 하네스 테스트

## 위험 등급

{chr(10).join(grade_rows)}

## 문제 정의

- 요청: 하네스 검증
- 실제 목표: 운영 변경의 회귀 방지
- 비목표: 돈 경로 변경 없음
- 위험: PR 본문 증거 누락
- 완료 기준: 검사 통과

## 탐색 근거

- 읽은 파일: AGENTS.md
- 확인한 실행 경로: scripts/check_pr_quality_gate.py
- 제거하거나 줄인 기능: 없음
- 남긴 기능 또는 대체 수단: 기존 품질 관문 유지

## 변경 내용

- 테스트 본문

## 검증

- [x] 문서 검증

## 하네스 검증

- 하네스 평가: {harness}

## 안전 경계

- Kernel 터치: 없음
- 안전 경계 변경: 없음
- 돈 경로 변경: 없음
- 감사 로그·비밀값·주문 제한 영향: 없음

## 인계

- 다음 세션이 알아야 할 상태: 없음
- 남은 위험: 없음
- 실행하지 못한 검증: 없음

## 자동 머지 준비

- [x] 작업 완료
"""


def _run_checker(body: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "pr_body.md"
    path.write_text(body, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_template_structure_passes():
    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--template",
            str(REPO / ".github" / "pull_request_template.md"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "pr-quality-gate-ok" in result.stdout


def test_grade_2_requires_strict_harness_evidence(tmp_path):
    result = _run_checker(_body(grade=2, harness="미실행"), tmp_path)

    assert result.returncode == 1
    assert "등급 2 이상 변경" in result.stderr


def test_grade_2_accepts_strict_harness_evidence(tmp_path):
    result = _run_checker(
        _body(
            grade=2,
            harness="`uv run python scripts/agent_harness_probe.py --strict` -> 통과",
        ),
        tmp_path,
    )

    assert result.returncode == 0
    assert "pr-quality-gate-ok" in result.stdout


def test_grade_1_allows_not_applicable_harness_evidence(tmp_path):
    result = _run_checker(_body(grade=1, harness="해당 없음"), tmp_path)

    assert result.returncode == 0
    assert "pr-quality-gate-ok" in result.stdout
