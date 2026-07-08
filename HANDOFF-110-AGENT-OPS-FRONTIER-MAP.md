# HANDOFF 110 — 운영 체계 frontier 지도 (2026-07-08 KST)

main 코드 베이스라인: `8a612ff`(PR #499). 이 작업은 스펙 105가 열어 둔
`candidate-agent-ops-frontier-map`을 완료 처리하고, 자율 작업 실행 루프가 handoff 사실성,
PR/머지 증거, worktree 동시 작업 방어 후보를 운영 체계 frontier로 재생성하게 한 등급 2 운영 체계
보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `agent_ops_frontier_map`을 JSON과 Markdown 보고서에 추가했다.
  - 운영 체계 하위 후보 3개를 고정했다:
    `candidate-handoff-truth-liveness-contract`,
    `candidate-pr-merge-evidence-liveness-contract`,
    `candidate-worktree-concurrency-liveness-contract`.
  - `candidate-agent-ops-frontier-map`이 released-work에 기록되면 첫 하위 후보
    `candidate-handoff-truth-liveness-contract`로 전진한다.
  - 모든 생성 후보는 위험 등급 2, 안전 영향 없음, 읽기 전용 work packet이다.
- `tests/unit/test_autonomous_work_execution.py`
  - 운영 체계 frontier 지도 결정론, Markdown 렌더링, 완료 뒤 후보 전진, 다음 후보 전진,
    위험 등급 2와 안전 영향 없음, required input을 고정했다.
- `specs/106-agent-ops-frontier-map/`
  - SDD 산출물과 `completed_candidate_id: candidate-agent-ops-frontier-map` 완료 마커를 남겼다.
- `.specify/feature.json`, `CLAUDE.md`
  - active feature pointer를 스펙 106으로 갱신했다.

## 운영상 의미

- 스펙 106 전에는 스펙 105가 닫힌 뒤 자율 루프가 `candidate-agent-ops-frontier-map`에서 한 번 멈췄다.
- 이제 스펙 106이 released-work에 잡히면 다음 자율 후보는
  `candidate-handoff-truth-liveness-contract`다.
- 다음 세션은 handoff 사실성, PR/머지 증거, worktree 동시 작업 방어 중 첫 후보인 handoff 사실성
  생존성 계약부터 진행하면 된다.
- 이 변화는 다음 작업 후보를 고르는 보고 루프만 바꾼다. 돈 경로는 계속 `PREVIEW_ONLY`이며 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #499 merge commit: `8a612ff2e6ae1b9dffbc55ac6e56675ddee9afc4`
- PR #499 feature commit: `a0b2e449b0e005ceeb2dbbd127c51bf166ab297c`
- 직전 main: `4c177f6`(PR #498, 스펙 105 인계)
- PR #499 post-merge runs:
  - `Deploy on merge to main` run `28910730317`: success
  - `Released work ledger` run `28910730320`: success
  - `Autonomous work execution loop` run `28910730295`: success
- released-work sidecar:
  - `commit=8a612ff2e6ae1b9dffbc55ac6e56675ddee9afc4`
  - `released_count=27`
  - `candidate-agent-ops-frontier-map` released 확인
- autonomous-work sidecar:
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-handoff-truth-liveness-contract`
  - title `HANDOFF 사실성 생존성 계약`
  - risk grade 2
  - safety impact 없음
  - run id `28910730295`, timestamp `2026-07-08T01:26:58Z`
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar 최신 run은 #499 배포의 직접 증거가 아니라 이전 schedule 실행 증거다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 자율 후보 판정

- `overall_status=EXECUTION_READY`
- `selected_work=candidate-handoff-truth-liveness-contract`
- `completed_candidate_id=candidate-agent-ops-frontier-map`
- 다음 운영 체계 frontier 후보:
  - `candidate-handoff-truth-liveness-contract` — open
  - `candidate-pr-merge-evidence-liveness-contract` — open
  - `candidate-worktree-concurrency-liveness-contract` — open

## 안전 경계

- 위험 등급: 2(읽기 전용 운영 체계 frontier 지도와 work packet 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #499 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py -q`
  -> 41 passed
- remote sidecar replay
  -> `candidate-agent-ops-frontier-map` selected,
  `agent_ops_frontier_map[0].recommended_candidate_id=candidate-handoff-truth-liveness-contract`
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-agent-ops-frontier-map` released 확인
- `uv run python scripts/autonomous_work_execution_probe.py --evidence-dir <latest-sidecars> --repo-root . --json`
  -> `candidate-handoff-truth-liveness-contract` selected work 확인
- `uv run pytest`
  -> 2554 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2554 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run pytest -q`
  -> 갱신 전 stale HANDOFF 때문에 하네스 2건 실패, `HANDOFF.md` 수정 후 재실행에서 2554 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `git diff --check`
  -> 통과

## 다음 세션 한 줄

스펙 106은 운영 체계 frontier 지도를 닫았고, 자율 작업 루프는 이제
`candidate-handoff-truth-liveness-contract`를 다음 등급 2 읽기 전용 후보로 제안한다.
