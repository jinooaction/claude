# Feature Specification: Micro GTAA Intent-Loss Gate

**Feature Branch**: `Codex/micro-gtaa-intent-loss-gate`  
**Created**: 2026-06-27  
**Status**: Implemented  
**Input**: User description: "micro GTAA가 실행됐다면 오히려 돈을 잃었을 신호가 확인됐으므로, 돈 잃을 가능성이 보이는 실주문 수행을 막아라."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 즉시 실주문 중단 (Priority: P1)

운영자는 최신 micro GTAA 거부 주문 기회손익이 손실 방향으로 나왔을 때 다음 스케줄에서 같은 전략이 실제 주문을 반복하지 않기를 원한다.

**Why this priority**: 실제 돈 경로가 이미 무장되어 있고, 다음 정규장 스케줄에서 같은 매수 주문을 다시 시도할 수 있으므로 우선 실주문 표면을 닫아야 한다.

**Independent Test**: micro GTAA 무장 센티넬을 읽었을 때 `armed:false`이고 실주문 가능 상태가 아니라고 판정되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 최신 micro GTAA 기회손익이 `INTENT_LOSS`였을 때, **When** 저장소의 무장 센티넬을 확인하면, **Then** micro GTAA는 드라이런 미리보기만 가능한 상태여야 한다.
2. **Given** 운영자가 ETF 거래 신청을 완료했더라도, **When** 다음 스케줄이 오면, **Then** 이번 변경 전까지는 수익 목적 실주문이 자동으로 재개되지 않아야 한다.

---

### User Story 2 - 손실 의도 신호 기반 자동 차단 (Priority: P1)

운영자는 나중에 누군가 micro GTAA를 다시 무장하더라도, 최신 기회손익 신호가 손실 방향이면 워크플로가 실주문 전에 스스로 멈추기를 원한다.

**Why this priority**: 단순 미무장 변경만으로는 이후 재무장 시 같은 실수 경로가 재발할 수 있다.

**Independent Test**: 최신 `opportunity_monitor.json`이 `latest_signal=INTENT_LOSS`이거나 `verdict=STRATEGY_REVIEW`일 때 live 단계가 실행 조건을 만족하지 못하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 최신 opportunity monitor가 `INTENT_LOSS`를 담고 있을 때, **When** micro GTAA 워크플로가 실행되면, **Then** preflight와 live 주문 단계는 차단되어야 한다.
2. **Given** 최신 opportunity monitor가 `STRATEGY_REVIEW`를 담고 있을 때, **When** micro GTAA 워크플로가 실행되면, **Then** 실주문은 제출되지 않고 차단 사유가 사이드카와 Telegram에 표시되어야 한다.
3. **Given** opportunity monitor가 없거나 평가 가능한 손실 신호가 없을 때, **When** 다른 기존 게이트가 모두 통과하면, **Then** 이 새 게이트만으로 실주문을 막지 않아야 한다.

---

### User Story 3 - 차단 실행이 손실 신호를 지우지 않음 (Priority: P2)

운영자는 차단된 스케줄이 "평가 가능한 거부 주문 없음" 기록을 덧붙여 이전 손실 신호를 지워버리지 않기를 원한다.

**Why this priority**: 차단 실행이 unvalued 기록을 추가하면 다음 스케줄에서 최신 신호가 `FLAT_OR_UNVALUED`로 바뀌어 차단이 풀릴 수 있다.

**Independent Test**: live 결과 JSON이 없는 실행에서는 기존 opportunity history를 그대로 요약하고 새 빈 기록을 append하지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 이전 history의 최신 평가가 `INTENT_LOSS`일 때, **When** live 단계가 차단되어 결과 JSON이 없으면, **Then** history는 새 빈 기록 없이 보존되어야 한다.
2. **Given** 차단된 실행이 사이드카를 발행할 때, **When** 운영자가 `LAST_RUN.md`를 읽으면, **Then** 차단 사유와 기존 누적 평가가 함께 보여야 한다.

### Edge Cases

- 최신 sidecar branch를 읽지 못하면 새 게이트는 보수적으로 기존 실주문 가능성을 추가로 좁히지 않는다. 단, 현재 센티넬은 미무장 상태라 실주문은 여전히 0건이다.
- 최신 monitor가 JSON 파싱 불능이면 차단 판정은 "monitor unavailable"로 기록하고 기존 게이트 흐름을 유지한다.
- 게이트 평가 스크립트 자체가 실패하면 workflow는 안전하게 닫힌다. 이 경우 `gate_evaluation_unavailable`로 기록하고 live 주문 조건을 만족시키지 않는다.
- 최신 signal이 `INTENT_GAIN` 또는 `FLAT_OR_UNVALUED`이면 이 게이트만으로 차단하지 않는다.
- live 단계가 실행되지 않은 run은 opportunity history에 빈 평가 기록을 추가하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST set the micro GTAA live sentinel to preview-only until strategy evidence justifies re-arming.
- **FR-002**: System MUST evaluate the latest micro GTAA opportunity monitor before preflight and before any broker order submission.
- **FR-003**: System MUST block micro GTAA live order submission when the latest monitor has `latest_signal=INTENT_LOSS`.
- **FR-004**: System MUST block micro GTAA live order submission when the latest monitor has `verdict=STRATEGY_REVIEW`.
- **FR-005**: System MUST surface the intent-loss gate decision in the micro GTAA sidecar and Telegram alert.
- **FR-006**: System MUST NOT append a no-live/no-valued fallback opportunity record when live orders were skipped or blocked.
- **FR-007**: System MUST preserve existing K1 position caps, K2 whitelist, K4 audit trail, K5 secret masking, regular-session preflight, cash preflight, circuit breaker, and manual capital limit.
- **FR-008**: System MUST keep missing or unreadable opportunity monitor data separate from a positive approval signal.
- **FR-009**: System MUST fail closed when the live workflow cannot evaluate the intent-loss gate decision file.
- **FR-010**: System MUST NOT tell operators that additional live samples will automatically accumulate while the latest `INTENT_LOSS` gate is blocking live order submission.

### Key Entities

- **Micro GTAA Arming Sentinel**: Repository file that declares whether micro GTAA can attempt real orders and with what maximum capital.
- **Opportunity Monitor Summary**: Latest cumulative rejected-order opportunity verdict, latest signal, counts, streaks, and next action.
- **Intent-Loss Gate Decision**: Per-run decision recording whether opportunity evidence allows or blocks a live attempt.
- **Micro GTAA Sidecar**: Published read surface containing the latest run summary, gate diagnostics, live result, opportunity history, and monitor summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The next micro GTAA run after this change submits zero broker orders unless the sentinel is explicitly re-armed and the intent-loss gate allows it.
- **SC-002**: A monitor with `latest_signal=INTENT_LOSS` blocks live submission in automated tests.
- **SC-003**: A blocked or skipped live run does not increase the number of opportunity history records.
- **SC-004**: Operator-facing sidecar and Telegram text include the intent-loss gate state and reason.
- **SC-005**: Full test and lint gates pass before merge.

## Assumptions

- The latest observed `INTENT_LOSS` is enough to stop further real-money attempts even though the monitor verdict is still `INSUFFICIENT_DATA`.
- Re-arming after strategy review is a separate operator decision and is out of scope for this change.
- This feature reduces real-money exposure; it does not introduce a new strategy, increase capital, widen the whitelist, or bypass existing safety gates.
