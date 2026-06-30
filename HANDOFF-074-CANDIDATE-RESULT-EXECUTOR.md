# HANDOFF 074 — 후보 결과 실행기 루프 (2026-06-30 KST)

main 베이스라인: `b827364`(PR #417). 후보 구현 공장이 만든 검증 패키지를 자동 실행해
기계 판독 가능한 candidate result evidence로 바꾸고, 다음 factory/promotion 루프가 소비할
`automation/candidate-implementation-results` sidecar를 발행하는 스펙 071을 출시했다.

## 무엇이 바뀌었나

- `specs/071-candidate-result-executor/`: 목표, 비목표, 안전 경계, 데이터 모델, 계약, quickstart, tasks를 남겼다.
- `src/auto_invest/analytics/candidate_result_executor.py`: `candidate_packages.json`을 읽고 후보별 result row를 만든다.
- `scripts/candidate_result_executor_probe.py`와 `auto-invest candidate-results`: 로컬·workflow에서 같은 결과 실행을 재현한다.
- `.github/workflows/candidate-result-executor.yml`: 매일 08:42 UTC와 관련 main push 때 `automation/candidate-implementation-results` sidecar를 발행한다.
- `.github/workflows/candidate-implementation-factory.yml`: 08:44 UTC second pass를 추가해 result sidecar를 promotion scan 전에 다시 먹는다.
- `promotion_loop.py`: strategy evidence가 아직 세 단계 모두 pass가 아니면 forward/canary evidence layer를 pass처럼 표시하지 않는다.
- `pipeline_liveness`: `candidate-result-executor`를 non-critical 감시 대상으로 등록했다.

## 운영상 의미

- 이제 루프는 `후보 발굴 -> 후보 구현 공장 -> 후보 결과 실행기 -> 후보 구현 공장 second pass -> 승격 분류 -> 승격 실행` 순서가 된다.
- 결과 실행기는 명령 문자열을 shell로 그대로 실행하지 않고, package kind별 allowlist에 맞는 no-live 검증 명령만 토큰화해 실행한다.
- 전략/포트폴리오 후보는 `historical_backtest`, `recent_oos`, `walk_forward`가 실제 결과에서 모두 `pass`일 때만 forward 등록 준비로 올라간다.
- 비전략 후보는 `factory_validation`만 보강하며 전략 evidence를 위조하지 않는다.
- 실패, 시간 초과, 데이터 부족은 `pending` 또는 `blocked`로 남는다. `pass`가 없으면 승격하지 않는다.

## 배포 후 실제 실행 증거

- `Deploy on merge to main` run `28421591710`: success, commit `b8273649b3c3c606daf2277475dbdde85343c482`
- `Candidate result executor` run `28421591693`: success, sidecar `automation/candidate-implementation-results`
- result executor summary: `overall_status=degraded`, `pass=4`, `pending=5`, `fail=0`, `blocked=0`
- `KIS smoke (autonomous)` run `28421591753`: success, `key_valid=true`, live broker smoke 4건 통과
- result sidecar 이후 수동 dispatch 검증:
  - `Candidate implementation factory` run `28421661580`: success
  - `Autonomous promotion loop` run `28421678189`: success
  - `Autonomous promotion actions` run `28421696576`: success, `registered=0`, `submitted=0`
  - `Pipeline liveness` run `28421719284`: success, overall `OK`, `candidate-result-executor=OK`

## 현재 후보 상태

- 전략/포트폴리오 후보 2개는 아직 세 전략 evidence가 모두 pass가 아니므로 `BACKTEST_REQUIRED`에 남는다.
- 비전략 후보는 `FACTORY_PACKAGE_READY`로 분리된다. forward paper나 돈 게이트로 자동 승격되지 않는다.
- promotion actions는 등록·제출할 후보가 없어 0건이 정상이다.

## 안전 경계

- 위험 등급: 2(운영 자동화 변경)
- 실제 주문 실행: 없음
- 브로커 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 배포는 dry-run worker 코드 반영이다. 실거래 전환이 아니다.
- `Backtest -> Canary -> Full` 순서는 유지된다. 백테스트 통과는 캐너리 후보 자격이지 실계좌 실행 검증 완료가 아니다.

## 검증

PR #417 머지 전:

- focused pytest 52 통과
- `uv run pytest` → 2351 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run auto-invest candidate-results --help` → 정상 출력
- `uv run python scripts/check_pr_quality_gate.py /tmp/candidate_result_executor_pr_body.md` → OK
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- PR 품질 관문 → success, mergeable, merge 방식으로 main에 병합

머지 후:

- deploy, KIS smoke, candidate result executor, factory, promotion loop, promotion actions, pipeline liveness 모두 success
- 최신 liveness sidecar overall `OK`

## 다음 세션 한 줄

스펙 071로 후보 검증 패키지는 더 이상 사람이 실행할 때까지 멈춰 있지 않다. 시스템이 no-live 검증을 돌려 result evidence를 발행하고, 통과하지 못한 후보는 fail-closed로 `pending`에 남긴다.
