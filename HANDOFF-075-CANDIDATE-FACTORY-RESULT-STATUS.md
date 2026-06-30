# HANDOFF 075 — 후보 공장 result status 보정 (2026-06-30 KST)

main 베이스라인: `0b743c2`(PR #419). 스펙 071 후보 결과 실행기 출시 뒤,
candidate factory가 result evidence를 소비할 때 비전략 후보의 no-live 검증 통과를
`evidence_passed`로 표시하지 못하던 상태 판독을 고쳤다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/candidate_factory.py`: package kind별 result 판독 helper를 추가했다.
- `tests/unit/test_candidate_factory.py`: 비전략 후보가 `factory_validation=pass`일 때
  `STATUS_EVIDENCE_PASSED`가 되는 회귀 테스트를 추가했다.
- 전략·포트폴리오 후보는 계속 세 필수 evidence(`historical_backtest`, `recent_oos`,
  `walk_forward`)가 모두 `pass`일 때만 통과로 세어야 한다.
- 비전략 후보는 전략 evidence를 요구하지 않고, no-live `factory_validation=pass`만
  `evidence_passed`로 세어 운영 상태를 정확히 보여준다.

## 운영상 의미

- result executor가 `pass=4`, `pending=5`를 발행했는데 factory가 모든 후보를
  `pending`처럼 보여 주는 혼동이 사라졌다.
- `evidence_passed`는 "돈 경로 승격"이 아니라 "해당 후보 package의 no-live 검증 증거가
  통과했다"는 뜻이다.
- 전략/포트폴리오 후보 2개는 여전히 세 전략 evidence가 모두 pass가 아니므로
  `BACKTEST_REQUIRED`에 남는다.
- 비전략 후보 4개는 no-live 검증 통과 증거가 있으므로 `evidence_passed`가 되지만,
  전략 후보가 아니어서 forward paper나 돈 게이트로 자동 등록되지 않는다.

## 배포 후 실제 실행 증거

- `Deploy on merge to main` run `28422210023`: success, commit `0b743c2b31a552e7ddeffef39c7a21eacea06e0c`
- `Candidate result executor` run `28422210017`: success, sidecar `automation/candidate-implementation-results`
- result executor summary: `overall_status=degraded`, `pass=4`, `pending=5`, `fail=0`, `blocked=0`
- `Candidate implementation factory` run `28422210026`: success, sidecar `automation/candidate-implementation-factory-last-run`
- factory summary: `overall_status=ok`, `evidence_passed=4`, `pending=5`, `ready=0`, `blocked=0`
- 후속 dispatch 검증:
  - `Autonomous promotion loop` run `28422336507`: success, commit `0b743c2`
  - `Autonomous promotion actions` run `28422350673`: success, `registered=0`, `submitted=0`
  - `Pipeline liveness` run `28422367089`: success, overall `OK`

## 안전 경계

- 위험 등급: 2(운영 자동화 표면 보정)
- 실제 주문 실행: 없음
- 브로커 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 배포는 dry-run worker 코드 반영이다. 실거래 전환이 아니다.
- `Backtest -> Canary -> Full` 순서는 유지된다.

## 검증

PR #419 머지 전:

- focused pytest 13 통과
- `uv run pytest` → 2351 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- PR 품질 관문 → success, mergeable, merge 방식으로 main에 병합

머지 후:

- deploy, candidate result executor, candidate factory, promotion loop, promotion actions, pipeline liveness 모두 success
- 최신 liveness sidecar overall `OK`
- 최신 KIS smoke는 #417 commit `b827364` 기준 success이며, #419 path에서는 새 KIS smoke가 트리거되지 않았다.

## 다음 세션 한 줄

후보 결과 실행기는 `pass=4/pending=5`를 냈고, 후보 공장은 그 결과를 소비해
`evidence_passed=4/pending=5`로 정확히 표시한다. `pending` 5개는 실패를 통과로 위조하지 않은
보류 상태이며, 현재 돈 경로로 새로 등록된 후보는 없다.
