# HANDOFF 113 — worktree 동시 작업 생존성 계약 (2026-07-10 KST)

main 코드 베이스라인: `75d7140`(PR #505). 이 작업은 스펙 108이 열어 둔
`candidate-worktree-concurrency-liveness-contract`를 완료 처리하고, 여러 Codex 세션이 같은
worktree, 브랜치, 파일 묶음을 만질 때 정상 경고와 쓰기 전 차단이 살아 있는지 후보 단위로
고정한 등급 2 운영 체계 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/worktree_concurrency_liveness.py`
  - `.codex/hooks.json`, `.githooks/pre-commit`, `.githooks/pre-push`,
    `scripts/local_concurrency_guard.py`, optional guard output, released-work completion,
    안전 경계를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다.
  - synthetic guard 평가로 clean check `OK`, conflict check `WARN`, conflict pre-commit/pre-push
    `BLOCK`, main 직접 commit/push `BLOCK`을 확인한다.
  - 복구 스냅샷 source surface가 `metadata.json`, `worktree.diff`, `index.diff`, `untracked/`를
    계속 포함하는지 확인한다.
  - `completed_candidate_id: candidate-worktree-concurrency-liveness-contract`,
    `next_candidate_id: candidate-agent-harness-regression-liveness-contract`를 명시한다.
- `scripts/worktree_concurrency_liveness_probe.py`
  - `--guard-check`, `--released-work`, `--json-out`, `--summary-out`을 받는 읽기 전용 probe를
    추가했다.
- `src/auto_invest/analytics/autonomous_work_execution.py`
  - 운영 체계 frontier 지도에 다음 후보
    `candidate-agent-harness-regression-liveness-contract`를 추가했다.
  - agent-ops required inputs에 local concurrency guard, hook files, harness task suites를 포함했다.
- `tests/unit/test_worktree_concurrency_liveness.py`
  - all-pass, runtime guard output 대기, malformed released-work 실패, hook 누락 실패,
    hook 순서 실패, guard failure output 실패를 고정했다.
- `tests/integration/test_worktree_concurrency_liveness_probe.py`
  - CLI가 JSON과 Markdown 산출물을 쓰는지 확인한다.
- `tests/unit/test_autonomous_work_execution.py`
  - 스펙 109 완료 뒤 자율 작업 루프가
    `candidate-agent-harness-regression-liveness-contract`로 전진하는 회귀를 추가했다.
- `specs/109-worktree-concurrency-liveness-contract/`
  - SDD 산출물과 완료 마커를 남겼다.
- `.specify/feature.json`, `CLAUDE.md`
  - active feature pointer를 스펙 109로 갱신했다.

## 운영상 의미

- 정상 `WARN`은 장애가 아니라 "같은 worktree에서 쓰지 말고 isolate 하라"는 살아 있는 보호 신호다.
- pre-commit/pre-push 경로는 같은 worktree, 같은 브랜치, 겹치는 dirty file, main 직접 commit/push를
  쓰기 전에 `BLOCK`해야 한다.
- 복구 스냅샷 표면은 dirty/risky 상태에서 사용자 변경을 되돌리지 않고 재구성할 수 있게 남아야 한다.
- 스펙 109가 released-work에 잡히면 다음 자율 후보는
  `candidate-agent-harness-regression-liveness-contract`다.
- 이 변화는 저장소 운영 증거와 다음 작업 후보만 바꾼다. 돈 경로는 계속 `PREVIEW_ONLY`이며
  실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #505 merge commit: `75d7140f85d6e494834234069d8db0438f922ec9`
- PR #505 feature commit: `34e494291584bfae68d8182a86555d1e89949f6c`
- 직전 main: `52c5a29`(PR #504, 스펙 108 인계)
- PR #505 post-merge runs:
  - `Deploy on merge to main` run `29094880198`: success
  - `Released work ledger` run `29094880183`: success
  - `Autonomous work execution loop` run `29094880148`: success
- released-work sidecar:
  - `commit=75d7140f85d6e494834234069d8db0438f922ec9`
  - `overall_status=OK`
  - `candidate-worktree-concurrency-liveness-contract` released 확인
- autonomous-work sidecar:
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-agent-harness-regression-liveness-contract`
  - title `agent harness 회귀 생존성 계약`
  - risk grade 2
  - safety impact 없음
  - run id `29094880148`, timestamp `2026-07-10T13:07:11Z`
- deploy status:
  - main commit의 `Deploy on merge to main` workflow run `29094880198`과 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 자율 후보 판정

- `overall_status=EXECUTION_READY`
- `selected_work=candidate-agent-harness-regression-liveness-contract`
- `completed_candidate_id=candidate-worktree-concurrency-liveness-contract`
- 운영 체계 frontier 상태:
  - `candidate-handoff-truth-liveness-contract` — released
  - `candidate-pr-merge-evidence-liveness-contract` — released
  - `candidate-worktree-concurrency-liveness-contract` — released
  - `candidate-agent-harness-regression-liveness-contract` — open

## 안전 경계

- 위험 등급: 2(읽기 전용 worktree 동시 작업 생존성 계약과 후보 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #505 머지 전:

- `uv run pytest tests/unit/test_worktree_concurrency_liveness.py tests/integration/test_worktree_concurrency_liveness_probe.py tests/unit/test_autonomous_work_execution.py -q`
  -> 43 passed
- `uv run python scripts/worktree_concurrency_liveness_probe.py --repo-root . --guard-check /tmp/local_concurrency_guard_check_109.txt --format json ...`
  -> static/hook/synthetic/runtime/safety gates PASS, pre-release released-work gate WAIT
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-worktree-concurrency-liveness-contract` released 확인
- `uv run python scripts/autonomous_work_execution_probe.py --evidence-dir /tmp/codex109-sidecars --repo-root . --json`
  -> `candidate-agent-harness-regression-liveness-contract` selected work 확인
- `uv run pytest`
  -> 2577 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `git diff --check`
  -> 통과
- PR 품질 관문
  -> success

인계 브랜치에서:

- `uv run pytest -q`
  -> 2577 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `git diff --check`
  -> 통과

## 다음 세션 한 줄

스펙 109는 worktree 동시 작업 생존성 계약을 닫았고, 자율 작업 루프는 이제
`candidate-agent-harness-regression-liveness-contract`를 다음 등급 2 읽기 전용 후보로 제안한다.
