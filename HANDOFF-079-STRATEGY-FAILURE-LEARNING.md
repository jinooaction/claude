# HANDOFF 079 — 전략 실패 학습 장부화 (2026-07-01 KST)

main 코드 베이스라인: `fa8cc32`(PR #428). 스펙 075는 promotion loop가 `DISCARD`로 판정한
전략/포트폴리오 후보를 autonomous evolution loop의 `learning_ledger.json`에 `rejected`로 남긴다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/evolution_loop.py`
  - 기본 evidence manifest에 `promotion-summary`를 추가했다.
  - `automation/autonomous-promotion-last-run:promotion_summary.json`을 읽어 `DISCARD` stage인
    `strategy_design`/`portfolio_design` 후보만 `PromotionFailureSignal`로 해석한다.
  - 실패 후보를 `learning_ledger.json`의 `decision=rejected` 항목으로 병합한다.
  - 기존 rejected 항목이 있으면 중복 생성하지 않는다.
  - promotion summary가 없거나 JSON이 깨졌으면 기존 evolution scan은 fail-open으로 계속 실행한다.
- `tests/unit/test_evolution_loop.py`
  - 두 운영 후보가 rejected ledger entry가 되는 경로를 검증한다.
  - 중복 방지와 malformed summary fail-open을 검증한다.
- `tests/integration/test_evolution_loop_probe.py`
  - `evolution_loop_probe.py --manifest`가 promotion summary sidecar를 수집하는지 검증한다.
- `specs/075-strategy-failure-learning/`
  - 문제 정의, 안전 경계, 계약, 데이터 모델, 작업 목록을 남겼다.

## 운영상 의미

- 가격 이력 부족은 스펙 074로 해소됐다.
- 두 후보는 이제 데이터 부족 후보가 아니라, 가격 이력을 넣어 검증했지만 no-edge/fail인 실패 후보다.
- promotion loop run `28504209238`은 두 후보를 `DISCARD`로 분류했다.
- autonomous evolution run `28507752974`는 이 `DISCARD` 결과를 학습 장부에 `rejected`로 흡수했다.
- 다음 세션은 `candidate-1ed634d8bf6d`, `candidate-cc96b35062da`를 다시 승격할 후보로 보지 않는다.
  새 전략/포트폴리오 아이디어는 새 후보로 만들고 `Backtest -> Canary -> Full` 순서로 검증한다.

## 배포 후 실제 실행 증거

- PR #428 merge commit: `fa8cc32353929993a050e0d8e1d088918ec2891e`
- `Deploy on merge to main` run `28507752817`: success, commit `fa8cc32`
- `Autonomous evolution loop` run `28507752974`: success, commit `fa8cc32`
- 최신 `origin/automation/autonomous-evolution-last-run:learning_ledger.json`
  - `candidate-1ed634d8bf6d`: `decision=rejected`,
    `evidence_package_id=autonomous-promotion:28504209238`
  - `candidate-cc96b35062da`: `decision=rejected`,
    `evidence_package_id=autonomous-promotion:28504209238`
- 최신 `candidate_backlog.json`
  - 두 후보 모두 `status=rejected`
  - 다음 행동은 "기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다."

## 안전 경계

- 위험 등급: 2(운영 자동화 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 기존 sidecar JSON을 읽고 evolution summary, candidate backlog, learning ledger를 쓰는 변경이다.
- `Backtest -> Canary -> Full` 순서는 유지된다.

## 검증

PR #428 머지 전:

- `uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py -q`
  -> 27 passed
- `uv run ruff check src/auto_invest/analytics/evolution_loop.py tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py`
  -> All checks passed
- 최신 sidecar local smoke -> `candidate-1ed634d8bf6d`, `candidate-cc96b35062da` 모두
  `rejected`, source `autonomous-promotion:28504209238`
- `uv run pytest` -> 2366 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `git diff --check` -> OK
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success, mergeable, merge 방식으로 main에 병합

머지 후:

- deploy run `28507752817`: success
- autonomous evolution run `28507752974`: success
- latest sidecar verification -> 두 후보가 `learning_ledger.json`, `candidate_backlog.json`,
  `evolution_summary.json`에서 `rejected`로 확인됨

## 다음 세션 한 줄

스펙 075는 실패한 두 전략/포트폴리오 후보를 autonomous evolution 학습 장부에 영구 `rejected`로 남겼다.
다음 작업은 이 둘의 재승격이 아니라 새 전략/포트폴리오 설계 후보를 만들고 같은 안전 순서로 검증하는 것이다.
