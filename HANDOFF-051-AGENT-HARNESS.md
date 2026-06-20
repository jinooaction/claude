# HANDOFF 051 — Codex 에이전트 하네스 평가·회귀·PR 증거 관문 (2026-06-20)

main 베이스라인: `cbc2cd4`(PR #368). 운영자 지시: "목표 스킬 사용해서 세계 최고 수준 하네스
만들어줘." 이번 세션은 목표 도구로 장기 목표를 만들고, Codex 작업 운영 체계를 등급 2 변경으로
강화했다. 헌법·커널·주문 제한·비밀값·배포 제한·돈 경로는 바꾸지 않았다.

## 무엇이 출시됐나

- **하네스 평가 명령**: `scripts/agent_harness_probe.py --strict`
  - 세션 시작 훅 순서(`local_concurrency_guard` → `git_ground_truth`)
  - `git_ground_truth`의 local-only 사실 출력과 `/sync` 안내
  - local concurrency guard의 `isolate`, pre-commit, pre-push 방어
  - PR 품질 관문 워크플로와 PR 본문 검사기
  - `AGENTS.md`, `.codex/quality-gate.md`, SDD feature pointer, `HANDOFF.md`
  - `.codex/harness/evaluation_tasks.toml` 회귀 과제 묶음
  - 최신 main 기준 결과: `OK (11/11)`
- **회귀 과제 묶음**: `.codex/harness/evaluation_tasks.toml`
  - 12개 대표 작업 시나리오
  - 위험 등급 0, 1, 2, 3, 4 모두 포함
  - context truth, concurrency, worktree isolation, SDD, PR quality, validation,
    safety boundary, handoff, rollback, external effects 범주 포함
- **PR 증거 관문**:
  - `.github/pull_request_template.md`에 `## 하네스 검증` 추가
  - `scripts/check_pr_quality_gate.py`가 등급 2 이상 PR에서
    `agent_harness_probe.py --strict` 증거를 요구
  - 등급 0~1은 하네스 평가를 "해당 없음"으로 둘 수 있지만, 필드 자체는 채워야 함
- **운영 규칙 반영**:
  - `AGENTS.md`와 `.codex/quality-gate.md`에 등급 2 이상 하네스 strict 평가 규칙 추가
  - `specs/056-agent-harness-eval/`에 spec, plan, research, data-model, quickstart,
    contract, tasks 기록

## 검증

- PR #368 머지 전:
  - `uv run pytest` → 2205 passed, 4 skipped
  - `uv run ruff check src tests` → All checks passed
  - `uv run ruff check scripts/agent_harness_probe.py scripts/check_pr_quality_gate.py
    tests/unit/test_agent_harness_probe.py tests/unit/test_check_pr_quality_gate.py` → All checks passed
  - `uv run python scripts/agent_harness_probe.py --strict` → `OK (11/11)`
  - `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`
    → `pr-quality-gate-ok`
  - `git diff --check` → 통과
- PR #368 원격:
  - `pr-quality-gate` GitHub Actions 체크 통과
  - `mergeStateStatus=CLEAN`, `mergeable=MERGEABLE`
- 머지 후 handoff 갱신 전 최신 main:
  - `uv run pytest -q` → 2205 passed, 4 skipped
  - `uv run ruff check src tests` → All checks passed

## 안전 경계

- 위험 등급: 2(운영 체계 변경)
- Kernel 터치: 없음
- 헌법 변경: 없음
- 주문 제한·비밀값·배포 제한·외부 API 안전장치 변경: 없음
- 돈 경로 변경: 없음
- 새 프로브는 로컬 파일만 읽고 네트워크, 브로커, 비밀값, 주문 경로를 사용하지 않음

## 다음 세션 한 줄

등급 2 이상 운영 변경을 할 때는 구현 전후로 `uv run python scripts/agent_harness_probe.py --strict`를
실행하고, PR 본문 `## 하네스 검증`에 결과를 남겨야 한다. 새 기능을 시작할 때는 기존대로
`/sync`, 최신 `HANDOFF.md`, 관련 Speckit 산출물을 먼저 확인한다.
