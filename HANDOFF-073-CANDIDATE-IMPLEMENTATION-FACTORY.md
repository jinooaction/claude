# HANDOFF 073 — 후보 구현 공장 자동화 (2026-06-29 KST)

main 베이스라인: `b395e83`(PR #414). `BACKTEST_REQUIRED`에 멈춘 자율 성장 후보를 후보별 검증 패키지와 enriched backlog로 변환하는 스펙 070을 출시했다.

## 무엇이 바뀌었나

- `specs/070-candidate-implementation-factory/`: 목표, 비목표, 안전 경계, 데이터 모델, 계약, quickstart, tasks를 남겼다.
- `src/auto_invest/analytics/candidate_factory.py`: candidate backlog와 optional result evidence를 읽어 후보별 implementation package와 `promotion_evidence` patch를 만든다.
- `scripts/candidate_factory_probe.py`와 `auto-invest candidate-factory`: 로컬·workflow에서 같은 factory state를 재현한다.
- `.github/workflows/candidate-implementation-factory.yml`: 매일 08:40 UTC와 관련 main push 때 `automation/candidate-implementation-factory-last-run` sidecar를 발행한다.
- `.github/workflows/autonomous-promotion-loop.yml`: candidate factory의 `candidate_backlog.enriched.json`을 raw evolution backlog보다 우선 읽는다.
- `promotion_loop.py`: 비전략 factory package는 `BACKTEST_REQUIRED`가 아니라 `FACTORY_PACKAGE_READY`로 분리한다.
- `pipeline_liveness`: `candidate-implementation-factory`를 non-critical 감시 대상으로 등록했다.

## 운영상 의미

- 이제 루프는 `후보 발굴 -> 후보 구현 공장 -> 승격 분류 -> 승격 실행` 순서가 된다.
- 전략/포트폴리오 후보는 실제 `historical_backtest`, `recent_oos`, `walk_forward` 결과가 모두 `pass`일 때만 forward 등록 준비로 올라간다.
- 운영·데이터·회고 후보는 더 이상 전략 백테스트 대기로 오해되지 않고, 구현 패키지 준비 상태로 분리된다.
- 결과 증거가 없으면 `pass`를 만들지 않는다. 패키지는 `ready`로 남고, 후보는 승격되지 않는다.

## 첫 실행 증거

- `Candidate implementation factory` run `28339636371`: success, commit `b395e83e4f2975a74a14a3a182383adf8cc9e422`
- sidecar: `automation/candidate-implementation-factory-last-run`
- push-trigger 첫 실행은 optional result evidence branch fetch가 같은 fetch 명령에 묶인 탓에 입력 수집이 비어 후보 0개를 발행했다. 후속 브랜치 `Codex/fix-candidate-factory-fetch`에서 automation wildcard fetch로 고쳤다.
- 로컬 smoke는 최신 sidecar 후보 9개를 모두 패키지화했다. 전략/포트폴리오 후보 2개는 `BACKTEST_REQUIRED`, 나머지 7개는 `FACTORY_PACKAGE_READY`로 분리됐다.

## 배포와 smoke

- `Deploy on merge to main` run `28339636369`: success
- `KIS smoke (autonomous)` run `28339636380`: success
- KIS smoke commit: `b395e83e4f2975a74a14a3a182383adf8cc9e422`
- `key_valid=true`, live broker smoke 4건 통과
- 배포는 dry-run worker 코드 반영이다. 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(운영 자동화 변경)
- 실제 주문 실행: 없음
- 브로커 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- `Backtest -> Canary -> Full` 순서는 유지된다. factory는 통과 증거를 위조하지 않고, 통과 후보만 기존 promotion action 경로로 넘긴다.

## 검증

PR #414 머지 전:

- focused pytest 40 통과
- 실제 최신 sidecar 후보 9개 smoke 통과
- enriched backlog promotion scan smoke 통과
- `uv run pytest` → 2342 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `git diff --check` → clean
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- PR 품질 관문 → success, mergeable, merge 방식으로 main에 병합

후속 fetch 보정 브랜치 기준:

- `uv run pytest tests/integration/test_candidate_factory_probe.py -q` → 4 passed
- `uv run ruff check tests/integration/test_candidate_factory_probe.py` → All checks passed
- `git diff --check` → clean

## 다음 세션 한 줄

자율 성장 후보는 이제 그냥 `BACKTEST_REQUIRED`에 쌓이지 않는다. 후보 구현 공장이 모든 후보를 실행 패키지로 나누고, 실제 결과 증거가 통과한 전략 후보만 다음 promotion 단계로 보낸다.
