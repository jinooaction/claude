# Feature Specification: Autonomous Macro Growth Discovery

**Feature Branch**: `Codex/088-autonomous-macro-growth-discovery`
**Created**: 2026-07-03
**Status**: Draft
**Input**: User description: "더 거시적인 관점에서 자율 자동 성장 루프 시스템을 만들 수 있도록 조사하고, 목표 스킬을 활용해 꼼꼼하게 진행한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 닫힌 후보 큐를 거시 후보로 승격 (Priority: P1)

운영자는 자율 작업 실행 루프가 모든 일반 후보를 `released` 또는 `suppressed`로 닫은 뒤에도 완료 후보를 `selected_work`처럼 보여주지 않고, "후보 공간이 고갈됐다"는 사실 자체를 새 자율 개선 후보로 올리기를 원한다.

**Why this priority**: 현재 루프는 정적 후보가 모두 완료·억제되면 실행 가능한 후보가 0개가 되고, 이미 완료된 후보가 선택 항목처럼 남아 다음 작업 판단을 흐린다.

**Independent Test**: 일반 후보가 모두 released-work로 닫힌 입력에서 자율 작업 실행 결과가 `candidate-macro-growth-discovery`를 `EXECUTION_READY`로 선택하면 검증된다.

**Acceptance Scenarios**:

1. **Given** 일반 후보가 전부 released-work 장부에 있음, **When** autonomous-work execution이 실행됨, **Then** 완료 후보 대신 거시 성장 후보가 실행 가능 후보로 선택된다.
2. **Given** 일반 실행 가능 후보가 하나라도 있음, **When** autonomous-work execution이 실행됨, **Then** 거시 후보는 끼어들지 않고 일반 후보가 선택된다.

---

### User Story 2 - 안전·복구 후보를 가리지 않음 (Priority: P2)

운영자는 거시 후보 발굴이 안전 경계 후보, 운영자 승인 후보, 입력 복구 후보를 덮어쓰지 않기를 원한다.

**Why this priority**: 세계 최고 수준의 자율성은 개입을 줄이되, 승인 필요 또는 복구 필요 상태를 "다음 후보가 생겼다"는 말로 숨기면 안 된다.

**Independent Test**: operator approval 후보 또는 pipeline repair 후보가 있을 때 거시 후보가 생성되지 않으면 검증된다.

**Acceptance Scenarios**:

1. **Given** 안전 경계 때문에 operator approval이 필요한 후보가 있음, **When** autonomous-work execution이 실행됨, **Then** 해당 후보가 선택되고 거시 후보는 선택되지 않는다.
2. **Given** 핵심 sidecar가 누락 또는 malformed임, **When** autonomous-work execution이 실행됨, **Then** 복구 후보가 먼저 선택된다.

---

### User Story 3 - 부트스트랩 완료 뒤 다음 거시 후보로 진행 (Priority: P3)

운영자는 이 작업 자체가 released-work로 닫힌 뒤에도 루프가 다시 빈 상태로 돌아가지 않고, 다음 거시 개선 후보를 순차적으로 제안하기를 원한다.

**Why this priority**: `candidate-macro-growth-discovery` 하나만 생성하면 이번 PR 이후 다시 "남은 후보 없음" 상태가 된다. 부트스트랩이 끝난 뒤 이어질 후보까지 결정론적으로 남겨야 다음 세션이 두 번 일하지 않는다.

**Independent Test**: released-work에 `candidate-macro-growth-discovery`가 이미 있으면 자율 작업 실행 결과가 `candidate-evolution-source-diversification`을 다음 후보로 선택하면 검증된다.

**Acceptance Scenarios**:

1. **Given** `candidate-macro-growth-discovery`가 released-work에 있음, **When** 일반 후보 큐가 닫힌 상태로 실행됨, **Then** 다음 거시 후보 `candidate-evolution-source-diversification`이 선택된다.
2. **Given** 모든 정의된 거시 후보까지 released-work에 있음, **When** 일반 후보 큐가 닫힌 상태로 실행됨, **Then** 루프는 거짓 후보를 만들지 않고 관찰 대기 또는 닫힌 상태를 보고한다.

### Edge Cases

- 모든 증거 sidecar가 누락된 경우에는 거시 후보가 아니라 pipeline-liveness 복구 후보가 우선한다.
- 후보가 operator approval 또는 blocked 상태이면 거시 후보가 이를 덮지 않는다.
- released-work가 malformed이면 완료 여부를 확정할 수 없으므로 기존 보수적 선택을 유지한다.
- 거시 후보는 읽기 전용 작업 패킷일 뿐이며 주문, 브로커 API, 자본 배분, live 전략, whitelist/caps, 비밀값, 헌법, 커널, 외부 유료 서비스를 바꾸지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect when the autonomous work queue has no `EXECUTION_READY` regular candidate and every remaining regular packet is closed as `RELEASED` or `SUPPRESSED`.
- **FR-002**: System MUST emit `candidate-macro-growth-discovery` as `EXECUTION_READY` when the regular queue is closed and this bootstrap candidate is not already released.
- **FR-003**: System MUST NOT emit macro-growth candidates when any regular packet is `EXECUTION_READY`, `OPERATOR_APPROVAL_REQUIRED`, or `BLOCKED`.
- **FR-004**: System MUST use released-work to skip already completed macro-growth candidates.
- **FR-005**: System MUST emit `candidate-evolution-source-diversification` after `candidate-macro-growth-discovery` is released and the regular queue is still closed.
- **FR-006**: System MUST keep macro-growth candidates risk grade 2, read-only, and inside the existing Codex SDD/PR/merge completion gates.
- **FR-007**: System MUST include source references that explain the closed queue signal: evolution backlog, released-work, pipeline liveness, and capital-path readiness.
- **FR-008**: System MUST publish a Speckit contract with `completed_candidate_id: candidate-macro-growth-discovery`.
- **FR-009**: System MUST verify focused unit behavior, probe behavior, released-work reproduction, full tests, lint, HANDOFF fact check, strict harness, and PR quality gate before merge.

### Key Entities *(include if feature involves data)*

- **Regular Work Packet**: Candidate-derived work packet from existing sidecars before macro synthesis.
- **Closed Queue Signal**: State where no regular execution-ready packet exists and all non-ready regular packets are released or suppressed.
- **Macro Growth Candidate**: Deterministic agent-ops candidate emitted only when the queue is closed.
- **Completed Candidate Marker**: Speckit contract field consumed by released-work after this feature ships.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With all regular candidates released, selected work is `candidate-macro-growth-discovery` and ranked work count is at least 1.
- **SC-002**: With `candidate-macro-growth-discovery` released and the regular queue still closed, selected work is `candidate-evolution-source-diversification`.
- **SC-003**: With a normal execution-ready candidate, selected work remains that normal candidate and no macro candidate appears in ranked work.
- **SC-004**: With an operator approval candidate, selected work remains operator approval and no macro candidate appears in ranked work.
- **SC-005**: `released_work_probe.py --repo-root .` includes `candidate-macro-growth-discovery` after tasks are checked complete and the explicit contract marker is present.
- **SC-006**: Focused tests, probe tests, full pytest, ruff, HANDOFF fact check, strict harness, and PR quality gate pass.
- **SC-007**: No changed file belongs to broker order submission, capital ladder authority, whitelist/caps, live strategy switching, secrets, constitution, or kernel manifest.

## Assumptions

- `autonomous_work_execution` is the right first integration point because it already sees released-work, learning ledger, pipeline liveness, and candidate sidecars together.
- This feature bootstraps macro discovery; the next emitted candidate should expand upstream evolution sources beyond static templates.
- The change is risk grade 2 because it changes autonomous next-work selection and next-session behavior, but it does not change the money path or safety perimeter.
