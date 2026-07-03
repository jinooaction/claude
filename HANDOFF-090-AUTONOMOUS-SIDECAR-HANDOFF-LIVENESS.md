# HANDOFF 090 — 자율 루프 sidecar와 HANDOFF 생존성 (2026-07-03 KST)

main 코드 베이스라인: `2de0f95`(PR #459). 이 작업은 자율 작업 실행 루프가 고른 `candidate-88a7e7f07361`를 닫은 등급 2 운영 자동화 보정이다. 이미 main에 존재하던 `autonomous-evolution` 생존 감시와 HANDOFF `/sync` 진입점을 완료 조건으로 인식하고, 동시에 뜨는 promotion/factory/result executor 자동화가 오래된 sidecar로 같은 후보를 되살리지 못하게 했다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/evolution_loop.py`
  - `pipeline-liveness`가 `autonomous-evolution=OK`를 담고 `HANDOFF.md`가 세션 시작 진입점과 `/sync` 경로를 담으면 `candidate-88a7e7f07361`를 `released`로 표시한다.
- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `released-work` 장부가 완료한 후보를 `RELEASED`로 억제하고 다음 착수 후보로 넘긴다.
- `src/auto_invest/analytics/promotion_loop.py`, `.github/workflows/autonomous-promotion-loop.yml`
  - 현재 체크아웃의 released-work 증거를 먼저 생성해 완료 후보를 `DISCARD`로 버린다.
- `src/auto_invest/analytics/candidate_factory.py`, `.github/workflows/candidate-implementation-factory.yml`
  - 완료 후보는 검증 패키지로 만들지 않는다.
- `src/auto_invest/analytics/candidate_result_executor.py`, `.github/workflows/candidate-result-executor.yml`
  - 오래된 `candidate_packages.json`에 완료 후보가 남아 있어도 현재 체크아웃의 released-work 장부를 기준으로 실행하지 않고 fresh result도 발행하지 않는다.
- `specs/086-autonomous-sidecar-handoff-liveness/`
  - `completed_candidate_id: candidate-88a7e7f07361` 계약, stale sidecar 재현 기준, result executor 후속 보정을 남겼다.

## 운영상 의미

- `candidate-88a7e7f07361`는 더 이상 새 자율 후보가 아니다. 최신 sidecar에서 released-work는 `released`, autonomous-work는 `RELEASED`, promotion은 `DISCARD`, factory/package/result 출력은 후보 없음이다.
- 다음 자율 작업 실행 sidecar의 선택 후보는 `candidate-fa66202bf496`다. 이 후보는 별도 작업으로 시작해야 하며, 스펙 086을 다시 구현하지 않는다.
- 이 작업은 자동화의 후보 판독과 완료 장부 소비를 바꾼다. 돈 경로, 주문, 자본, live 전략, 허용 종목, 포지션 한도는 바꾸지 않는다.

## 배포 후 실제 실행 증거

- PR #457 merge commit: `671b1a7f0a6846e34467eac22f7c38a147f8e99a`
- PR #458 merge commit: `e8779c8666516d550e4c6e815033f9aa3c46dcad`
- PR #459 merge commit: `2de0f951234d3073932fb347b44004f5507cabd8`
- PR #459 post-merge runs:
  - `Deploy on merge to main` run `28629315303`: success
  - `Released work ledger` run `28629315307`: success
  - `Autonomous work execution loop` run `28629315301`: success
  - `Candidate implementation factory` run `28629315287`: success
  - `Candidate result executor` run `28629315296`: success
- 최신 sidecar 재확인:
  - released-work commit `2de0f95`, `candidate-88a7e7f07361` status `released`
  - autonomous-work commit `2de0f95`, `candidate-88a7e7f07361` status `RELEASED`, selected work `candidate-fa66202bf496`
  - promotion sidecar commit `e8779c8`, `candidate-88a7e7f07361` stage `DISCARD`
  - candidate factory commit `2de0f95`, package output에 `candidate-88a7e7f07361` 없음
  - candidate result executor commit `2de0f95`, executor output와 `candidate_results.json`에 `candidate-88a7e7f07361` 없음

## 안전 경계

- 위험 등급: 2(운영 자동화 후보 판독 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #457 머지 전:

- focused pytest 66 passed
- `uv run pytest` -> 2444 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success

PR #458 머지 전:

- focused pytest 31 passed
- stale promotion/factory local replay -> promotion `DISCARD`, factory package 후보 없음
- `uv run pytest` -> 2446 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success

PR #459 머지 전:

- `uv run pytest tests/unit/test_candidate_result_executor.py tests/integration/test_candidate_result_executor_probe.py -q` -> 14 passed
- stale result package local replay -> `result-executor-stale-suppression-ok`
- `uv run pytest` -> 2447 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `git diff --check` -> pass
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success

인계 브랜치에서:

- `uv run ruff check src tests` -> All checks passed
- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #458을 최신 main으로 가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- `HANDOFF.md`를 #459 main 기준으로 갱신한 뒤 `uv run python scripts/check_handoff_facts.py` -> OK
- `HANDOFF.md`를 #459 main 기준으로 갱신한 뒤 `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- `HANDOFF.md`를 #459 main 기준으로 갱신한 뒤 `uv run pytest -q` -> 2447 passed, 4 skipped

## 다음 세션 한 줄

스펙 086의 `candidate-88a7e7f07361`는 main과 sidecar에서 완료·억제 상태로 닫혔다. 다음 세션은 이 후보를 다시 구현하지 말고, 자율 작업 실행 sidecar가 고른 `candidate-fa66202bf496`를 새 SDD 작업으로 시작하면 된다.
