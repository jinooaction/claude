# Feature Specification: Broad NO_EDGE Frontier

**Feature Branch**: `124-broad-no-edge-frontier`
**Created**: 2026-08-11
**Status**: Draft
**Input**: User description: "좋아 그럼 다음 작업도 이어서 목표 스킬 활용해서 진행해줘" after autonomous-work selected `candidate-broad-frontier-expansion-no-edge-58298dfc172c`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - broad 후보가 자기 반복하지 않음 (Priority: P1)

운영자는 `NO_EDGE_YET` 뒤에 발행된 broad frontier 후보를 완료했을 때 같은 종류 후보가 지문만 바뀌어 다시 선택되지 않기를 원한다.

**Why this priority**: 같은 후보가 반복되면 돈 경로를 넓히지 못하고 작업 루프가 제자리걸음한다.

**Independent Test**: 모든 기존 후보가 닫히고 `candidate-broad-frontier-expansion-no-edge-<fingerprint>`가 released-work에 기록된 fixture에서 새 broad 후보가 아니라 다음 no-live 실험 후보가 선택되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 기존 macro, frontier, nested 후보와 broad no-edge 후보가 모두 released-work에 있음, **When** autonomous-work가 같은 `PREVIEW_ONLY` / `NO_EDGE_YET` 증거를 읽음, **Then** broad no-edge 후보를 다시 발행하지 않는다.
2. **Given** broad no-edge 후보만 아직 released-work에 없음, **When** 기존 후보가 모두 닫히고 no-edge 증거가 남아 있음, **Then** 기존 broad no-edge 후보를 그대로 선택한다.

---

### User Story 2 - broad 완료 뒤 다음 no-live 실험 축을 선택함 (Priority: P2)

운영자는 broad frontier 확장을 완료한 뒤 막연히 새 증거를 기다리는 대신, 전략군·신호군·보유 기간·자산군·레짐·비용·데이터 결측을 포함한 다음 실험 후보를 보고 싶다.

**Why this priority**: 돈을 바로 움직이지 못하는 상태에서도 안전하게 할 수 있는 최단 경로는 검증 가능한 no-live 실험 축을 계속 생성하는 것이다.

**Independent Test**: broad no-edge 후보가 released-work에 있고 no-edge 증거가 유지되는 fixture에서 `broad_no_edge_frontier_map`의 첫 미완료 항목이 `EXECUTION_READY`로 선택되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** broad no-edge 후보가 released-work에 기록됨, **When** `money-path`가 `PREVIEW_ONLY` / `NO_EDGE_YET`이고 `edge-autoarm`이 `WAIT_EDGE` / `NO_EDGE`임, **Then** 첫 broad no-edge 실험 후보를 선택한다.
2. **Given** 첫 broad no-edge 실험 후보가 released-work에 기록됨, **When** 같은 no-edge 증거가 유지됨, **Then** 다음 broad no-edge 실험 후보를 선택한다.

---

### User Story 3 - 안전 경계를 그대로 보존함 (Priority: P3)

운영자는 "당장 돈 벌기"를 원하지만, 이 작업이 실주문·자본 배분·live 재무장을 승인하지 않는다는 점이 보고와 산출물에 남아야 한다.

**Why this priority**: `NO_EDGE_YET` 상태에서 주문 게이트를 우회하면 우연한 성과를 검증된 엣지로 착각할 수 있다.

**Independent Test**: 새 후보와 지도 항목의 `risk_grade`, `safety_boundary`, `required_inputs`, markdown 보고에 주문·자본·live 변경 금지가 유지되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** broad no-edge 실험 후보가 선택됨, **When** 보고 JSON과 markdown을 확인함, **Then** 실제 주문, live 재무장, 자본 배분이 금지된 안전 경계가 포함된다.
2. **Given** `EDGE_CONFIRMED`가 증거에 나타남, **When** autonomous-work가 다음 후보를 선택함, **Then** no-edge broad 후보를 no-edge 근거로 발행하지 않는다.

### Edge Cases

- released-work가 broad no-edge 후보 자신 또는 broad no-edge 후속 후보를 추가해도 parent broad 후보 지문은 바뀌지 않아야 한다.
- retryable 검증 실패 패키지가 있으면 기존 validation-failure broad 후보가 우선이며, no-edge 후속 실험 후보가 이를 가리지 않아야 한다.
- 모든 증거가 missing이면 broad no-edge 후보를 새로 만들지 않아야 한다.
- 이미 선택 가능한 일반 후보, 운영자 승인 후보, blocked 후보가 있으면 broad 후속 후보가 앞지르지 않아야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST keep `candidate-broad-frontier-expansion-no-edge-<fingerprint>` stable after that exact candidate is recorded in released-work.
- **FR-002**: The system MUST exclude broad no-edge parent and follow-up candidate IDs from the no-edge parent fingerprint input.
- **FR-003**: The system MUST expose a deterministic `broad_no_edge_frontier_map` in JSON and markdown reports.
- **FR-004**: The broad no-edge map MUST cover strategy family, signal family, holding period, asset universe, regime windows, cost sensitivity, and data missing causes.
- **FR-005**: The system MUST emit the first unreleased broad no-edge map candidate after a broad no-edge parent candidate is released and current evidence still indicates `PREVIEW_ONLY`, `NO_EDGE_YET`, `NO_EDGE`, `WAIT_EDGE`, or `ACCUMULATING_EDGE`.
- **FR-006**: The system MUST NOT emit broad no-edge follow-up candidates when an execution-ready, blocked, or operator-approval candidate already exists.
- **FR-007**: The system MUST NOT treat broad no-edge follow-up candidates as permission for broker API calls, orders, live strategy changes, capital allocation, whitelist/caps changes, secret access, or external paid service use.

### Key Entities

- **BroadNoEdgeFrontierMapEntry**: A deterministic row describing one no-live experiment axis, its recommended candidate, coverage status, required inputs, and safety-preserving next action.
- **StableNoEdgeFingerprint**: The parent broad no-edge candidate fingerprint derived from no-edge context and released-work state while ignoring broad no-edge parent/follow-up releases.
- **BroadNoEdgeFollowUpPacket**: The actual `EXECUTION_READY` work packet emitted from the first unreleased map entry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Focused autonomous-work tests prove the broad no-edge parent does not reappear with a new fingerprint after it is released.
- **SC-002**: Focused autonomous-work tests prove the first and second broad no-edge map entries are selected in order as released-work records completion.
- **SC-003**: The markdown report contains a `광역 no-edge frontier 지도` section with deterministic row ordering.
- **SC-004**: Full repository validation passes before merge: `uv run pytest`, `uv run ruff check src tests`, `scripts/check_handoff_facts.py`, and `scripts/agent_harness_probe.py --strict`.

## Assumptions

- The current correct money-path state is still `PREVIEW_ONLY` / `NO_EDGE_YET`; this feature does not try to change it.
- This is a grade 2 operating-loop change, not a grade 4 live-money action.
- Existing released-work is the source of truth for candidate completion.
- The fastest safe path is to widen no-live experiment generation, not to lower the edge threshold or submit orders.
