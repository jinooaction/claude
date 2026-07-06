# HANDOFF 106 — 체결 품질 frontier 지도 (2026-07-07 KST)

main 코드 베이스라인: `c975517`(PR #491). 이 작업은 스펙 101이 열어 둔
`candidate-execution-quality-frontier-map`을 완료 처리하고, 체결 품질 영역 안쪽의 다음 읽기 전용 후보를
브로커 거부 분류, 체결 비용 기준, 브로커 진단 생존성으로 지도화한 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - `execution_quality_frontier_map`을 JSON과 Markdown에 추가했다.
  - 지도는 세 후보를 순서대로 연다.
    - `candidate-broker-rejection-taxonomy-contract`
    - `candidate-execution-cost-basis-contract`
    - `candidate-broker-diagnostic-liveness-contract`
  - `candidate-execution-quality-frontier-map`이 released-work에 기록되면 첫 후보
    `candidate-broker-rejection-taxonomy-contract`로 전진한다.
  - KIS smoke Markdown 표를 구조화해 `smoke_state`와 `smoke_exit`를 evidence surface에서 읽는다.
- `scripts/autonomous_work_execution_probe.py`
  - `execution-quality`, `kis-smoke`, `rebalance-micro-gtaa` sidecar를 manifest에 추가했다.
- `tests/unit/test_autonomous_work_execution.py`
  - 체결 품질 지도 결정론, Markdown 렌더링, released frontier 뒤 후보 전진,
    브로커 거부 후보 뒤 체결 비용 기준 후보 전진을 고정했다.
- `tests/integration/test_autonomous_work_execution_probe.py`
  - manifest와 probe 출력이 새 sidecar와 `execution_quality_frontier_map`을 포함하는지 검증한다.
- `specs/102-execution-quality-frontier-map/`
  - SDD 산출물과 `completed_candidate_id: candidate-execution-quality-frontier-map` 완료 마커를 남겼다.

## 운영상 의미

- 최신 remote released-work sidecar는 `candidate-execution-quality-frontier-map`을 released로 읽는다.
- 최신 remote autonomous-work sidecar는 다음 실행 후보를
  `candidate-broker-rejection-taxonomy-contract`로 선택한다.
- 다음 후보는 `execution-quality`, `rebalance-micro-gtaa`, `kis-smoke` 증거를 함께 읽어 브로커 거부 코드,
  원인, 재발 가능성을 분류하는 읽기 전용 계약이다.
- 돈 경로는 계속 `PREVIEW_ONLY`이고 실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #491 merge commit: `c9755170b8a1972c63e45a1e6d7a30e7fbfc5dd0`
- PR #491 feature commit: `5b81ab0`
- 직전 main: `3e56ce9`(PR #490, 스펙 101 인계)
- PR #491 post-merge runs:
  - `Deploy on merge to main` run `28829134863`: success
  - `Released work ledger` run `28829134911`: success
  - `Autonomous work execution loop` run `28829134839`: success
- released-work sidecar:
  - timestamp `2026-07-06T23:01:23.747012Z`
  - `candidate-execution-quality-frontier-map` 포함
  - released count 23
- autonomous-work sidecar:
  - timestamp `2026-07-06T23:01:25Z`
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-broker-rejection-taxonomy-contract`
  - domain `execution_quality`
  - risk grade 2, safety impact 없음
- deploy status:
  - main commit의 `Deploy on merge to main` 체크와 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar 최신 run은 #491 배포의 직접 증거가 아니라 이전 schedule 실행 증거이므로 #491 배포
    근거로 쓰지 않는다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 체결 품질 frontier 지도

| 영역 | 상태 | 점수 | 추천 후보 | 이유 |
|------|------|-----:|-----------|------|
| 브로커 거부 분류 | open | 2150 | `candidate-broker-rejection-taxonomy-contract` | execution-quality sidecar는 거부 주문과 KIS 오류 코드를 관측하지만, 거부 원인 분류와 재발 기준은 별도 후보로 닫혀 있지 않다. |
| 체결 비용 기준 | open | 2050 | `candidate-execution-cost-basis-contract` | 비용 차감 엣지 후보는 execution-quality를 읽지만, accepted fill 비용 기준의 충분성은 아직 독립 후보로 닫혀 있지 않다. |
| 브로커 진단 생존성 | open | 1950 | `candidate-broker-diagnostic-liveness-contract` | KIS smoke와 execution-quality는 신선도와 성공 상태를 보여주지만, 체결 품질 후보 관점의 PASS/WAIT/FAIL 계약은 아직 분리돼 있지 않다. |

## 안전 경계

- 위험 등급: 2(읽기 전용 체결 품질 후보 지도와 work packet 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #491 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py -q`
  -> 36 passed
- remote sidecar replay
  -> selected candidate `candidate-execution-quality-frontier-map`, 첫 지도 후보
  `candidate-broker-rejection-taxonomy-contract`, `execution-quality`/`kis-smoke`/`rebalance-micro-gtaa`
  evidence surface parse OK
- tasks 완료 상태 released-work local replay
  -> `candidate-execution-quality-frontier-map` released 확인
- tasks 완료 상태 autonomous-work local replay
  -> `candidate-broker-rejection-taxonomy-contract` selected work 확인
- `uv run pytest`
  -> 2526 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `git diff --check`
  -> 통과
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/check_pr_quality_gate.py .verify/pr-102-execution-quality-frontier-map.md`
  -> pr-quality-gate-ok
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2526 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run pytest -q`
  -> 2526 passed, 4 skipped

## 다음 세션 한 줄

스펙 102는 체결 품질 frontier를 지도화해 닫았고, 자율 작업 후보는 이제
`candidate-broker-rejection-taxonomy-contract`로 전진한다.

