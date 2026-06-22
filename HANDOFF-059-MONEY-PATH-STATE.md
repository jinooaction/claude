# HANDOFF 059 — 스펙 062 money-path 실제 돈 최상위 상태 (2026-06-22)

main 베이스라인: `3440001`(PR #384). 운영자가 오늘 실제 돈 투입 상태를 물었을 때,
최근 코드와 실행 증거에서 `micro GTAA armed:true`를 먼저 확인하지 못한 사고를 재발하지 않도록
money-path의 최상위 상태 표면을 고쳤다. 이 작업은 상태 판독과 인계 보강이며 실제 주문 실행이나
자본 증액이 아니다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/money_path.py`: `LiveMoneyState`와 `MicroGtaaRunEvidence`를 추가하고,
  JSON schema version을 `1.1`로 올렸다.
- money-path text report는 이제 `## 실제 돈 최상위 상태`를 기존 자본 사다리 상태보다 먼저 보여준다.
- `scripts/money_path_probe.py`: `automation/rebalance-micro-gtaa.request`와
  `rebalance-micro-gtaa-last-run` sidecar를 읽는다.
- `.github/workflows/money-path.yml`: micro GTAA request와 workflow 변경도 money-path 발행 트리거에
  포함했다.
- `specs/062-money-path-state/`: 문제 정의, 계획, 연구 기록, 데이터 모델, 계약, quickstart, tasks를
  추가했다.
- `HANDOFF.md`: 다음 세션이 오래된 역사 문단이나 KIS smoke 현금값이 아니라 money-path
  `live_money_state`를 먼저 보도록 필수 판독 규칙을 상단에 추가했다.

## 현재 운영 상태

- `automation/rebalance-micro-gtaa.request`는 `armed:true`, `capital_usd:1000` 상태다.
- 스펙 062 로컬 재현 기준 `live_money_state.status=REAL_ORDER_PATH_ARMED`,
  `can_submit_real_orders=true`, `capital_usd=1000`이다.
- 다음 예약 live 후보는 재현 시각 `2026-06-22T12:55:00Z` 기준 `2026-06-22T15:00:00Z`였다.
  그 이후 세션은 반드시 최신 `origin/automation/money-path-last-run` 또는
  `origin/automation/rebalance-micro-gtaa-last-run`을 다시 읽는다.
- 마지막 micro GTAA 실행 `run_id=27935469561`은 `event=workflow_dispatch`, `live_step=success`였지만
  브로커 주문 상태는 `REJECTED_BY_BROKER` 2건이고 접수·체결은 0건이다.
- 따라서 "실제 돈 경로가 켜져 있음"은 맞지만, "주문이 접수·체결됨"은 아니다.

## 안전 경계

- 위험 등급: 2(운영 상태 판독과 인계 변경)
- 돈 경로 변경: 없음
- 실제 주문 실행: 없음
- 자본 증액 또는 배분 변경: 없음
- live 전략 변경: 없음
- 주문 라우터·브로커 제출·체결 동기화 변경: 없음
- K1 캡, K2 화이트리스트, K4 감사 로그 추가 기록, K5 비밀값 분리, K6 장중 배포 제한 변경: 없음
- preflight, 손실 브레이커, 시장시간 조건은 기존 micro GTAA workflow가 계속 담당한다.

## 검증

PR #384 머지 전:

- `uv run pytest tests/unit/test_money_path.py tests/integration/test_money_path_probe.py tests/unit/test_micro_gtaa_canary.py` → 84 passed
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'` 후
  `scripts/money_path_probe.py --manifest` 기반 로컬 재현 → `live_money_state.status=REAL_ORDER_PATH_ARMED`
- `uv run pytest` → 2249 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `git diff --check` → OK
- PR 품질 관문 통과

머지 직전:

- `uv run pytest` → 2249 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- PR #384 상태: ready, `mergeStateStatus=CLEAN`, remote `pr-quality-gate` success

handoff 갱신 직전:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패했다. 코드 실패가 아니라
  `HANDOFF.md` 마지막 main 커밋 행이 `3440001`로 갱신되지 않은 문제였다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2249 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

실제 돈 상태를 물으면 먼저 money-path의 `live_money_state.status`와
`automation/rebalance-micro-gtaa.request`를 확인한다. 현재 원본 기준 micro GTAA는
`armed:true`, `capital_usd:1000`이며, 마지막 실행은 live step까지 갔지만 브로커 거부 2건·접수체결
0건이었다.
