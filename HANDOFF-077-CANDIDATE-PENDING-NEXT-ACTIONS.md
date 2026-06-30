# HANDOFF 077 — 후보 pending next action 보정 (2026-07-01 KST)

main 베이스라인: `0de15a4`(PR #423). 스펙 072가 진단한 pending 5개 중 자동화 배선으로
해결 가능한 3개를 실제 pass로 줄이고, 가격 이력 부족 2개는 거짓 통과 없이 pending으로 남겼다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/candidate_factory.py`
  - `ops_liveness` 후보 명령을 `pipeline_liveness_probe.py --sidecar-dir /tmp/candidate_result_sidecars --strict --json`로 고쳤다.
  - `analytics_validation` 후보 명령을 `auto-invest macro-regime --data-dir /tmp/candidate_result_public_data --json`로 고쳤다.
  - `data_quality` 후보가 기본 `data/auto_invest.db`에 의존하지 않고 pipeline liveness sidecar 검증을 실행하게 했다.
- `src/auto_invest/analytics/candidate_result_executor.py`
  - `data_quality` 후보에서도 `scripts/pipeline_liveness_probe.py` no-live 명령 표면을 허용했다.
  - 기존 `bars-status` 허용 표면은 과거/다른 data quality 패키지 호환을 위해 유지했다.
- `.github/workflows/candidate-result-executor.yml`
  - 후보 패키지 실행 전에 pipeline liveness sidecar들을 `/tmp/candidate_result_sidecars`에 준비한다.
  - `automation/public-data` snapshot을 `/tmp/candidate_result_public_data`에 준비한다.
- `specs/073-candidate-pending-next-actions/`
  - spec, plan, research, data-model, quickstart, support input contract, tasks를 추가했다.

## 운영상 의미

- result executor가 더 이상 이전 패키지의 아래 오류를 반복하지 않는다.
  - `pipeline_liveness_probe.py --json`처럼 `--sidecar-dir`가 빠진 명령
  - `macro-regime --format json`처럼 현재 CLI에 없는 옵션
  - data quality 후보가 준비되지 않은 기본 `data/auto_invest.db`를 읽다가 실패하는 경로
- 자동으로 해결 가능한 pending 3개는 no-live 검증 통과로 줄었다.
- 전략/포트폴리오 후보 2개는 과거 가격 이력이 없어 계속 pending이다. 이건 다음 스펙에서 안전한
  가격 이력 수집 또는 `ingest-history` 실행 경로로 풀어야 한다.

## 배포 후 실제 실행 증거

- `Deploy on merge to main` run `28474687085`: success, commit `0de15a4bcd125bbbf1c259fc098f61fbf9496cc0`
- main push 직후 `Candidate result executor` run `28474687229`: success였지만, factory sidecar 갱신보다
  먼저 패키지를 읽어 이전 패키지 명령을 실행했다.
- 새 factory sidecar가 발행된 뒤 재실행한 `Candidate result executor` run `28474761904`: success,
  sidecar `automation/candidate-implementation-results`
- 최신 result executor summary:
  - `overall_status=degraded`
  - `pass=7`, `pending=2`, `fail=0`, `blocked=0`
  - `diagnostic_counts`: `data_history_missing=2`, `insufficient_pass_evidence=1`
  - `command_contract_error=0`, `execution_failed=0`
- result sidecar 뒤 재실행한 `Candidate implementation factory` run `28474828027`: success,
  sidecar `automation/candidate-implementation-factory-last-run`
- 최신 factory summary:
  - `evidence_passed=7`, `pending=2`, `ready=0`, `blocked=0`

## 후보별 현재 상태

- `candidate-1ed634d8bf6d` strategy_backtest
  - 상태: pending
  - 진단: `data_history_missing`, `insufficient_pass_evidence`
  - 다음 행동: 안전한 가격 이력 dataset 또는 `ingest-history` 경로 준비, machine-readable verdict 보강
- `candidate-cc96b35062da` portfolio_backtest
  - 상태: pending
  - 진단: `data_history_missing`
  - 다음 행동: 안전한 가격 이력 dataset 또는 `ingest-history` 경로 준비
- `candidate-88a7e7f07361` ops_liveness
  - 상태: evidence_passed
  - 이전 문제: `command_contract_error`
  - 해결: sidecar dir를 명시한 pipeline liveness strict JSON 검증
- `candidate-e481b0309206` analytics_validation
  - 상태: evidence_passed
  - 이전 문제: `command_contract_error`
  - 해결: public-data dir를 명시한 `macro-regime --json` 검증
- `candidate-6ee3370e933d` data_quality
  - 상태: evidence_passed
  - 이전 문제: 기본 DB 부재로 `execution_failed`
  - 해결: sidecar freshness no-live 검증으로 대체

## 후속 루프 검증

최신 result/factory sidecar를 소비하도록 아래 workflow를 재실행했고 모두 성공했다.

- `Candidate result executor` run `28474761904`: success
- `Candidate implementation factory` run `28474828027`: success
- `Autonomous promotion loop` run `28474881043`: success, commit `0de15a4`

promotion summary는 전략/포트폴리오 후보 2개만 `BACKTEST_REQUIRED`로 남기고, 비전략 후보 7개는
`FACTORY_PACKAGE_READY`로 분류한다. 돈 경로로 새로 등록된 후보는 없다.

## 안전 경계

- 위험 등급: 2(운영 자동화 보정)
- 실제 주문 실행: 없음
- 브로커 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 배포는 dry-run worker 코드 반영이다. 실거래 전환이 아니다.
- `Backtest -> Canary -> Full` 순서는 유지된다.
- 최신 KIS smoke sidecar는 run `28426196361`, commit `419fbf7`, `smoke_state=success`,
  `key_valid=true`다. #423과 같은 commit의 KIS smoke는 아니므로 배포 성공의 직접 증거로 쓰지 않는다.

## 검증

PR #423 머지 전:

- `uv run pytest tests/unit/test_candidate_factory.py tests/unit/test_candidate_result_executor.py tests/integration/test_candidate_result_executor_probe.py`
  → 20 passed
- current-sidecar local smoke → `pass=7`, `pending=2`,
  `diagnostic_counts={"data_history_missing": 2, "insufficient_pass_evidence": 1}`
- `uv run pytest` → 2358 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `git diff --check` → OK
- Ruby `Psych.load_file(".github/workflows/candidate-result-executor.yml")` → OK
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- PR 품질 관문 → success, mergeable, merge 방식으로 main에 병합

머지 직전:

- `uv run pytest` → 2358 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

머지 후:

- deploy, result executor 재실행, candidate factory 재실행, promotion loop 재실행 모두 success
- 최신 result/factory/promotion sidecar는 commit `0de15a4` 기준으로 갱신됨

## 다음 세션 한 줄

후보 pending 5개 중 자동화 배선 문제 3개는 pass로 줄었다. 남은 실제 작업은 전략/포트폴리오
후보 2개를 위한 안전한 가격 이력 수집 또는 `ingest-history` 실행 경로 설계다.
