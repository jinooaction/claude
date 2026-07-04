# Feature Specification: Macro Candidate Map Regenerator

**Feature Branch**: `Codex/093-macro-candidate-map-regenerator`
**Created**: 2026-07-04
**Status**: Draft
**Input**: User description: "더 거시적 방향으로 후보가 고갈되지 않는 상위 생성 체계를 만들자. 목표 스킬로 꼼꼼하게 진행."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 후보 고갈 뒤 다음 실행 후보 재생성 (Priority: P1)

운영자는 자율 작업 실행 루프가 모든 기존 후보와 frontier 후보를 완료 처리한 뒤에도 "할 일이 없음"으로 멈추지 않고, 더 거시적인 미탐색 영역에서 다음 실행 가능한 후보를 받는다.

**Why this priority**: 최신 autonomous-work sidecar는 ranked 후보 0개와 released 후보만 남긴다. 이 상태를 반복하면 운영자가 매번 다음 후보를 직접 발굴해야 하므로 자율 성장 루프의 핵심 목적이 끊긴다.

**Independent Test**: 모든 기존 macro 후보, frontier 후보, 그리고 이번 regenerator 후보가 released-work에 기록된 입력을 넣으면 새 `EXECUTION_READY` 후보가 하나 이상 선택되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 일반 후보와 기존 macro 후보와 frontier 후보가 모두 released로 닫힌 상태, **When** autonomous-work 실행 보고서를 생성하면, **Then** `candidate-investment-edge-frontier-map`이 `EXECUTION_READY`로 선택된다.
2. **Given** 일반 실행 후보가 이미 존재하는 상태, **When** autonomous-work 실행 보고서를 생성하면, **Then** 거시 후보 지도 후보는 기존 실행 후보를 가리지 않는다.

---

### User Story 2 - 후보 영역별 거시 지도 제공 (Priority: P2)

다음 세션은 단순히 후보 ID 하나만 보지 않고, 투자 엣지·데이터 증거·체결 품질·운영 체계 영역 중 어디가 닫혔고 어디가 다음 탐색 대상인지 한눈에 본다.

**Why this priority**: 후보 재생성은 단일 후보를 만드는 데서 끝나면 다시 정적 큐가 된다. 영역별 지도는 왜 그 후보가 다음인지 재현하게 해 준다.

**Independent Test**: 동일 sidecar 입력을 두 번 실행했을 때 거시 후보 지도와 선택 후보가 결정론적으로 같고, JSON과 Markdown에 영역별 상태가 모두 나타나는지 확인한다.

**Acceptance Scenarios**:

1. **Given** released·suppressed 후보가 여러 영역에 분포한 상태, **When** 보고서를 생성하면, **Then** 각 영역의 closed/ready/suppressed count와 추천 후보가 기계 판독 JSON에 포함된다.
2. **Given** 보고서를 Markdown으로 렌더링하면, **When** 운영자가 HANDOFF 없이 읽어도, **Then** 다음 후보가 왜 선택됐는지 영역별 표에서 확인할 수 있다.

---

### User Story 3 - 안전 경계와 완료 후보 소비 유지 (Priority: P3)

시스템은 거시 후보를 재생성하더라도 돈 경로, 주문, live 전략, 허용 종목, 비밀값, 헌법·커널을 건드리지 않고 기존 released-work와 operator approval 규칙을 유지한다.

**Why this priority**: 후보 생성 자동화가 안전 경계를 우회하면 자율 성장 루프가 오히려 위험해진다.

**Independent Test**: 안전 표면 후보나 operator approval 후보가 있을 때 거시 후보 지도가 해당 후보를 자동 실행 후보로 덮어쓰지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 안전 표면이 있는 후보가 입력에 존재하는 상태, **When** 보고서를 생성하면, **Then** 그 후보는 기존처럼 `OPERATOR_APPROVAL_REQUIRED`로 남고 거시 재생성 후보가 끼어들지 않는다.
2. **Given** 거시 재생성 후보가 released-work로 완료 처리된 상태, **When** 보고서를 생성하면, **Then** 같은 후보를 다시 선택하지 않고 다음 미완료 frontier 후보로 넘어간다.

### Edge Cases

- 모든 sidecar가 없으면 기존 pipeline-liveness 복구 후보가 우선하며 거시 후보 지도는 실행 후보를 만들지 않는다.
- pipeline-liveness가 CRITICAL이면 복구 후보가 우선한다.
- recommended frontier 후보가 released-work에 이미 있으면 다음 우선순위 영역 후보로 넘어간다.
- 영역별 후보는 위험 등급 2, 안전 표면 없음인 읽기 전용 운영 후보로만 생성된다.
- 완료된 후보가 `selected_work`에 보일 수 있는 상태는 새 착수 후보가 아니라 closed 상태로 표기해야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect when normal candidates, existing macro candidates, frontier discovery, and macro candidate map regenerator are all closed by released-work or suppression.
- **FR-002**: System MUST emit a deterministic macro candidate map with at least investment edge, data evidence, execution quality, and agent operations domains.
- **FR-003**: System MUST select the highest-priority unreleased domain frontier candidate when the existing candidate queue is closed after the regenerator itself is released.
- **FR-004**: System MUST keep existing regular execution candidates, operator approval candidates, blocked candidates, and pipeline repair candidates ahead of regenerated macro candidates.
- **FR-005**: System MUST expose the macro candidate map in machine-readable JSON and human-readable Markdown.
- **FR-006**: System MUST mark this work's completed candidate as `candidate-macro-candidate-map-regenerator`.
- **FR-007**: System MUST avoid real orders, broker API calls, capital allocation, live strategy changes, whitelist/caps changes, secret reads or writes, external paid services, constitution changes, and kernel changes.
- **FR-008**: System MUST preserve released-work consumption so released regenerated candidates are not selected again.

### Key Entities

- **Macro Candidate Map**: A deterministic list of high-level exploration domains, each with current queue coverage, priority, and recommended next candidate.
- **Map Entry**: One domain row containing domain key, label, coverage status, counts, recommendation, reason, and next action.
- **Regenerated Candidate**: A generated work packet derived from the highest-priority map entry not already completed.
- **Completed Candidate Marker**: The SDD contract value that released-work reads to close this spec's implementation candidate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With all known macro and frontier implementation candidates released, the report produces at least one `EXECUTION_READY` regenerated candidate.
- **SC-002**: With the same input evidence, two report generations produce identical macro candidate map JSON and selected candidate.
- **SC-003**: Existing focused autonomous-work tests and integration probe tests all pass after the change.
- **SC-004**: Full repository tests, lint, PR quality gate, HANDOFF fact check, and strict agent harness pass before merge.
- **SC-005**: Latest post-merge sidecar can be interpreted without operator intervention: either it shows a new regenerated `EXECUTION_READY` candidate or a documented closed state in HANDOFF.

## Assumptions

- The correct implementation surface is the existing read-only autonomous-work execution report, not a new workflow that opens PRs or writes code automatically.
- Domain frontier candidates are work packets for Codex to implement through the existing SDD, PR, validation, merge, and HANDOFF path.
- The first regenerated frontier should bias toward investment edge because recent work mainly improved operating-system quality and the operator's long-term objective is measured financial growth.
- The change is risk grade 2 because it changes the autonomous next-work selection surface, but it does not touch safety boundaries or money paths.
