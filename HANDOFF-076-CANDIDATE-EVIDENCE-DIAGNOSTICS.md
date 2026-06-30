# HANDOFF 076 — 후보 증거 진단 루프 (2026-07-01 KST)

main 베이스라인: `e00ef09`(PR #421). 후보 결과 실행기가 `pending`으로 남긴 후보들의
원인을 기계 판독 가능한 진단과 다음 행동으로 분해하고, 후보 공장이 그 값을 enriched backlog로
전파하도록 고쳤다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/candidate_result_executor.py`
  - 후보별 result row에 `diagnostics`, `next_actions`, `retryable`을 추가했다.
  - `CandidateResultExecutorRun` JSON과 Markdown에 `diagnostic_counts`와 `진단 집계`를 추가했다.
  - `data_history_missing`, `command_contract_error`, `insufficient_pass_evidence`,
    `execution_failed`, `timeout`, `unsafe_command`, `unsupported_package`, `missing_command`,
    `missing_input`을 구분한다.
- `src/auto_invest/analytics/candidate_factory.py`
  - result evidence에서 `diagnostics`, `next_actions`, `retryable`을 읽는다.
  - enriched backlog의 `promotion_evidence`에 `factory_diagnostics`,
    `factory_next_actions`, `factory_retryable`을 전파한다.
  - `blocked` result는 후보 package도 blocked로 반영한다.
- `specs/072-candidate-evidence-diagnostics/`
  - `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`,
    `contracts/candidate-evidence-diagnostics.md`, `tasks.md`, requirement checklist를 추가했다.

## 운영상 의미

- 이제 `pending=5`는 "그냥 대기"가 아니다. 각 후보가 왜 못 올라가는지 다음처럼 분해된다.
  - 과거 데이터 준비 필요
  - 검증 명령 인자 계약 보정 필요
  - 실행은 됐지만 승격용 통과 증거 부족
  - 검증 명령 실패 원인 좁히기 필요
- 후보 공장과 승격 루프는 pass/pending/blocked뿐 아니라 보강 필요 이유와 재시도 가능성을
  자동 소비할 수 있다.
- 이 변경은 승격 기준을 낮추지 않는다. 전략/포트폴리오 후보는 계속
  `historical_backtest`, `recent_oos`, `walk_forward`가 모두 실제 result evidence에서
  `pass`일 때만 forward 등록 준비로 올라간다.

## 배포 후 실제 실행 증거

- `Deploy on merge to main` run `28455400890`: success, commit `e00ef096288dc31253918bc685725a17b18d660e`
- `Candidate result executor` run `28455402752`: success, sidecar `automation/candidate-implementation-results`
- result executor summary:
  - `overall_status=degraded`
  - `pass=4`, `pending=5`, `fail=0`, `blocked=0`
  - `diagnostic_counts`: `command_contract_error=2`, `data_history_missing=2`,
    `execution_failed=1`, `insufficient_pass_evidence=1`
- result sidecar 뒤 재실행한 `Candidate implementation factory` run `28455608750`: success,
  sidecar `automation/candidate-implementation-factory-last-run`
- factory enriched backlog summary:
  - 후보 9개 중 5개가 `factory_diagnostics`를 가진다.
  - 진단 코드는 result executor와 같은 집계다.

## 후보별 현재 다음 행동

- `candidate-1ed634d8bf6d` strategy_backtest
  - 진단: `data_history_missing`, `insufficient_pass_evidence`
  - 다음 행동: `prepare_history_dataset`, `emit_machine_readable_verdict`
  - 재시도 가능: true
- `candidate-cc96b35062da` portfolio_backtest
  - 진단: `data_history_missing`
  - 다음 행동: `prepare_history_dataset`
  - 재시도 가능: true
- `candidate-88a7e7f07361` ops_liveness
  - 진단: `command_contract_error`
  - 다음 행동: `repair_candidate_package_command`
  - 재시도 가능: false
- `candidate-e481b0309206` analytics_validation
  - 진단: `command_contract_error`
  - 다음 행동: `repair_candidate_package_command`
  - 재시도 가능: false
- `candidate-6ee3370e933d` data_quality
  - 진단: `execution_failed`
  - 다음 행동: `inspect_validation_failure`
  - 재시도 가능: true

## 후속 루프 검증

최신 result/factory sidecar를 소비하도록 아래 workflow를 재실행했고 모두 성공했다.

- `Autonomous promotion loop` run `28455673993`: success, commit `e00ef09`
- `Autonomous promotion actions` run `28455707966`: success, `registered=0`, `submitted=0`, `blocked=0`
- `Pipeline liveness` run `28455738048`: success, overall `OK`

`Pipeline liveness`는 아래 후보 자동화 sidecar를 모두 `OK`로 봤다.

- `autonomous-promotion`
- `candidate-implementation-factory`
- `candidate-result-executor`
- `autonomous-promotion-actions`

## 안전 경계

- 위험 등급: 2(운영 자동화 진단 보강)
- 실제 주문 실행: 없음
- 브로커 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 배포는 dry-run worker 코드 반영이다. 실거래 전환이 아니다.
- `Backtest -> Canary -> Full` 순서는 유지된다.

## 검증

PR #421 머지 전:

- `uv run pytest tests/unit/test_candidate_result_executor.py tests/unit/test_candidate_factory.py tests/integration/test_candidate_result_executor_probe.py -q`
  → 18 passed
- 최신 sidecar 입력 로컬 smoke → `pass=4`, `pending=5`, 진단 집계 재현
- `SPECIFY_FEATURE=072-candidate-evidence-diagnostics .specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks`
  → SDD 산출물 확인
- `uv run pytest -q` → 2356 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run auto-invest candidate-results --help` → OK
- PR 품질 관문 → success, mergeable, merge 방식으로 main에 병합

머지 후:

- deploy, candidate result executor, candidate factory, promotion loop, promotion actions,
  pipeline liveness 모두 success
- 최신 liveness sidecar overall `OK`
- 최신 KIS smoke sidecar는 run `28426196361`, commit `419fbf7`, `smoke_state=success`,
  `key_valid=true`다. #421과 같은 commit의 KIS smoke는 아니므로 배포 성공의 직접 증거로 쓰지 않는다.

## 다음 세션 한 줄

후보 결과 실행기는 이제 `pending`을 원인과 다음 행동으로 분해하고, 후보 공장은 그 진단을
enriched backlog로 전파한다. 현재 남은 자동 보강 대상은 과거 데이터 준비 2건, 검증 명령 계약
보정 2건, 검증 실패 원인 좁히기 1건이며, 돈 경로로 새로 등록된 후보는 없다.
