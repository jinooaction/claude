# Feature Specification: Money Path State Guard

**Feature Branch**: `Codex/money-path-state-guard`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: User description: "최근 작업과 현재 실제 돈 경로 상태 판단이 어렵고 토큰을 많이 쓰며, 실제 돈 투입 상태를 잘못 답한 것은 시스템 붕괴 수준의 위험이다. 다음 세션이 두 번 일하지 않게 목표 스킬로 해결하라."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Immediate Live Money State (Priority: P1)

운영자와 다음 세션은 최신 인수인계 역사 전체를 뒤지지 않고, 현재 실제 돈 경로가 무장되어 있는지, 다음 실제 주문 가능 실행이 언제인지, 얼마까지 주문할 수 있는지를 한 화면에서 먼저 확인해야 한다.

**Why this priority**: 실제 돈 경로 상태를 잘못 판독하면 운영자가 같은 사실 확인을 다시 시키게 되고, 더 나쁘게는 실거래 상태를 오해한 채 의사결정한다. 이 기능의 최우선 가치는 "지금 실제 돈이 켜져 있는가"를 즉시 답하는 것이다.

**Independent Test**: `micro GTAA` 센티넬이 `armed:true`인 저장소 상태와 최신 사이드카를 입력했을 때, 보고서가 첫 문단에서 실제 돈 경로가 무장되어 있고 다음 비-push 스케줄이 실주문을 시도할 수 있음을 표시한다.

**Acceptance Scenarios**:

1. **Given** `micro GTAA` 센티넬이 `armed:true`이고 자본이 1,000달러 이하일 때, **When** 돈 경로 상태 보고가 생성되면, **Then** 보고서 최상단은 `실제 돈 경로 무장`과 다음 예약 live 실행 시각을 표시한다.
2. **Given** 같은 상태에서 마지막 run이 브로커 거부로 끝났을 때, **When** 보고서를 읽으면, **Then** "실제 주문 경로 진입"과 "브로커 접수·체결 0건"을 구분해 표시한다.
3. **Given** 센티넬이 `armed:false`일 때, **When** 보고서가 생성되면, **Then** 실주문 가능 상태가 아니라 미리보기 전용임을 표시한다.

---

### User Story 2 - Evidence Priority Over History (Priority: P2)

에이전트는 오래된 `HANDOFF.md` 역사 문구나 KIS 스모크의 보조 정보를 먼저 해석하지 않고, 현재 돈 경로 판단에 필요한 단일 증거 묶음을 우선해야 한다.

**Why this priority**: 이번 사고는 최신 실제 돈 상태보다 보조 현금 수치와 오래된 문맥을 앞세워 발생했다. 상태 판독 순서가 문서와 검증으로 고정되어야 재발하지 않는다.

**Independent Test**: 상태 보고 입력에 `micro GTAA` 센티넬, 마이크로 실행 사이드카, 기존 자본 사다리 사이드카가 함께 있을 때, 보고서가 `micro GTAA` live 무장 상태를 기존 첫-자본 ETA보다 위에 표시한다.

**Acceptance Scenarios**:

1. **Given** 기존 자본 사다리는 단0이고 micro GTAA는 `armed:true`일 때, **When** 상태 보고가 생성되면, **Then** "기존 사다리는 대기 중"보다 "별도 마이크로 실거래 경로가 켜짐"이 먼저 나온다.
2. **Given** 최신 sidecar가 preflight 전 상태이거나 이전 run 형식일 때, **When** 보고서가 생성되면, **Then** 확인 불가능한 항목은 불명으로 표시하고 무장 상태 자체는 센티넬 기준으로 확정한다.

---

### User Story 3 - Regression Guard for Agent Reasoning (Priority: P3)

저장소는 에이전트가 다시 실제 돈 경로를 누락하지 못하도록 자동 테스트와 인수인계 규칙을 제공해야 한다.

**Why this priority**: 사람에게 "다시 확인해 달라"고 요구하지 않으려면, 돈 경로 상태 표면이 테스트로 고정되어야 한다.

**Independent Test**: 단위·통합 테스트가 `armed:true` micro GTAA 상태에서 보고서 JSON과 텍스트에 실제 돈 상태 필드를 요구하고, 누락 시 실패한다.

**Acceptance Scenarios**:

1. **Given** `micro GTAA` live 경로가 추가되거나 workflow 이름이 바뀔 때, **When** 테스트가 실행되면, **Then** money-path 보고서가 해당 경로를 소비하지 않으면 실패한다.
2. **Given** 다음 세션이 `HANDOFF.md`를 읽을 때, **When** 돈 경로 상태를 판단하려 하면, **Then** 최신 money-path 사이드카와 `automation/rebalance-micro-gtaa.request`를 먼저 보라는 명시적 안내를 확인한다.

### Edge Cases

- `automation/rebalance-micro-gtaa.request`가 없거나 파싱 불능이면 실제 돈 상태를 `UNKNOWN`으로 표시하고 단정하지 않는다.
- `armed:true`지만 자본이 1,000달러를 넘으면 실주문 가능이 아니라 `BLOCKED`로 표시한다.
- 마지막 micro GTAA sidecar가 #378 이전 형식이라 preflight 섹션이 없어도 보고서가 깨지지 않고 "preflight evidence absent"로 표시한다.
- `push` 이벤트의 마지막 run은 미리보기 전용이므로, 마지막 run이 `push`였다는 사실과 다음 스케줄의 live 가능성을 구분한다.
- KIS 스모크의 현금 값은 보조 정보일 뿐이며, `armed` 여부와 다음 live 가능 상태를 대체하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a top-level live-money state in the money-path report before the existing first-capital ladder stage.
- **FR-002**: System MUST read the `micro GTAA` arming sentinel and classify `armed:true` with valid capital as a real-order-capable path, subject to preflight and safety gates.
- **FR-003**: System MUST read the latest `micro GTAA` sidecar when available and summarize last trigger, live step outcome, broker order states, and preflight evidence.
- **FR-004**: System MUST distinguish "real order path entered" from "broker accepted or filled orders".
- **FR-005**: System MUST compute or state the next scheduled non-push live attempt for the micro GTAA workflow using the existing weekday 15:00 UTC schedule.
- **FR-006**: System MUST keep this feature read-only: no orders, no broker calls, no secret reads, no capital changes, no whitelist changes, and no workflow dispatch.
- **FR-007**: System MUST fail safe when evidence is missing by marking unknown or blocked fields instead of inferring from stale prose.
- **FR-008**: System MUST add automated tests that fail if the money-path manifest stops consuming the micro GTAA sidecar or if `armed:true` is not surfaced in the top-level state.
- **FR-009**: System MUST update handoff guidance so current money path state is read from the generated status surface before historical sections.
- **FR-010**: System MUST preserve existing capital ladder, K1 caps, K2 whitelist, K4 append-only audit, K5 secret isolation, K6 market-hours deploy guard, and the micro GTAA preflight gates unchanged.

### Key Entities

- **Live Money State**: The current top-level classification of whether any path can submit real orders, its capital ceiling, next possible live execution, and required gates.
- **Micro GTAA Request**: The operator-approved arming sentinel with `armed`, `capital_usd`, stop thresholds, stage, sequence, and note.
- **Micro GTAA Last Run Evidence**: The latest sidecar record containing run id, trigger, live step outcome, preflight result, breaker result, and order states.
- **Money Path Report**: The existing read-only report that combines ladder, forward, canary, and now micro GTAA evidence into one status surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can answer "can the system try real orders tonight?" from the first report section without reading historical handoff sections.
- **SC-002**: The report JSON contains a `live_money_state` object with `status`, `can_submit_real_orders`, `capital_usd`, `next_scheduled_live_utc`, and last-run evidence fields.
- **SC-003**: The report text for the current `armed:true` micro GTAA state contains both `실제 돈 경로 무장` and `preflight 통과 후 실주문 가능`.
- **SC-004**: Automated tests cover `armed:true`, `armed:false`, invalid capital, missing sidecar, and old sidecar formats.
- **SC-005**: Full repository validation passes: focused tests, `uv run pytest`, and `uv run ruff check src tests`.

## Assumptions

- The current operator approval remains limited to micro GTAA `capital_usd=1000`; this feature does not approve larger capital.
- The weekday `15:00 UTC` micro GTAA schedule remains the source of the next automatic live attempt unless the workflow changes.
- Existing Telegram alerts and audit log observers are complementary outputs; the single status surface still lives in money-path because it already aggregates money readiness.
- This feature is a reporting and reasoning guard, not a trading strategy change.
