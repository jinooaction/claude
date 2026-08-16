# Feature Specification: Live Money Route Priority

**Feature Branch**: `Codex/142-live-money-route-priority`
**Created**: 2026-08-16
**Status**: In Progress
**Risk Grade**: 2 - 읽기 전용 돈 경로 상태 집계와 다음 세션 판단 변경

## User Scenarios & Testing

### User Story 1 - 실제 주문 가능한 경로를 최상위에 표시하기 (Priority: P1)

운영자는 표준 자본 사다리 live-canary가 단 1·무장 상태인데 비무장 micro 경로 때문에
`PREVIEW_ONLY`로 보이는 모순 없이, 지금 실제 주문 단계에 도달할 수 있는 경로를 먼저 보고 싶다.

**Independent Test**: 표준 센티넬이 `armed:true`, 단 1, 자본 293달러이고 표준 sidecar도
무장인 반면 micro 센티넬은 비무장일 때 최상위 상태는 `REAL_ORDER_PATH_ARMED`, 경로는
`capital-ladder-live-canary`, 자본은 293달러여야 한다.

### User Story 2 - 여러 실거래 경로를 같은 보수 기준으로 비교하기 (Priority: P1)

운영자는 표준과 micro 경로 중 하나를 이름으로 고정 우선하지 않고, 실제 주문 가능·차단·미리보기·
불명 순으로 평가하기를 원한다. 어느 경로든 무장 증거가 불완전하면 실주문 가능으로 표시하면 안 된다.

**Independent Test**: 표준 센티넬과 sidecar 무장 값 불일치, 잘못된 자본·단, 센티넬 누락을 각각
주입하면 `BLOCKED` 또는 `UNKNOWN`이고, 표준 비무장·micro 무장 조합에서는 micro 경로가 선택된다.

## Requirements

- **FR-001**: 표준 live 경로는 `automation/rebalance-live.request`를 권위 센티넬로 읽어야 한다.
- **FR-002**: 표준 경로의 `armed`, `capital_usd`, `ladder_rung`, `account_nav_usd`를 검증해야 한다.
- **FR-003**: 센티넬 무장과 최신 live-canary sidecar 무장이 다르면 실패 폐쇄해야 한다.
- **FR-004**: 경로 우선순위는 `REAL_ORDER_PATH_ARMED > BLOCKED > PREVIEW_ONLY > UNKNOWN`이어야 한다.
- **FR-005**: 동률이면 현재 자본 사다리 표준 경로를 우선해 기존 사다리 표와 기준을 맞춰야 한다.
- **FR-006**: 표준 경로의 다음 예약, production 승인, 정규장, 현금, 손실 브레이커, K1/K2를 표시해야 한다.
- **FR-007**: micro 경로가 실제 무장이고 표준 경로가 비무장이면 기존 micro 경로를 유지해야 한다.
- **FR-008**: 이 기능은 주문, 자본, 센티넬, 허용 목록, 안전 게이트를 변경하지 않는 읽기 전용이어야 한다.

## Success Criteria

- **SC-001**: 현재 실제 sidecar 재생에서 최상위 상태가 `REAL_ORDER_PATH_ARMED`로 바뀐다.
- **SC-002**: 현재 최상위 경로는 `capital-ladder-live-canary`, 자본 293달러, 다음 예약
  `2026-08-17T15:00:00Z`를 기록한다.
- **SC-003**: 표준 무장 불일치와 micro 무장 보존 회귀가 각각 통과한다.
- **SC-004**: 전체 pytest, ruff, diff, 엄격 하네스, HANDOFF 사실, PR 품질 관문을 통과한다.
- **SC-005**: 머지 뒤 money-path와 capital-path-readiness sidecar를 현재 main으로 재발행한다.

## Safety And Rollback

이 기능은 보고 우선순위만 바꾸며 주문과 자본을 움직이지 않는다. 센티넬 또는 sidecar 증거가
불완전하면 실주문 가능으로 추정하지 않는다. 문제가 생기면 기능 커밋을 revert하고 직전 sidecar를
근거로 사용하되 감사 로그와 기존 거래 기록은 삭제하지 않는다.

completed_candidate_id: candidate-live-money-route-priority
next_candidate_id: observe-first-live-execution
