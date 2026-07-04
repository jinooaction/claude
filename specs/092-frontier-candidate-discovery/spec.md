# Feature Specification: Frontier Candidate Discovery

**Feature Branch**: `Codex/092-frontier-candidate-discovery`
**Created**: 2026-07-04
**Status**: Draft
**Input**: User description: "스펙 091 이후 자율 작업 실행 루프가 새 `EXECUTION_READY` 후보 없이 released 후보를 `selected_work`처럼 보여주는 상태를 닫고, 후보 고갈 자체를 다음 frontier 발굴 작업으로 승격한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 후보 고갈을 실행 가능한 frontier 작업으로 드러내기 (Priority: P1)

운영자는 자율 작업 실행 보고서가 모든 일반 후보와 기존 macro 후보를 닫은 뒤에도 `RELEASED` 후보를 다음 작업처럼 보여주지 않고, "새 frontier 후보를 발굴해야 한다"는 실행 가능한 작업을 발행하기를 원한다.

**Why this priority**: 스펙 091 이후 최신 sidecar는 `ranked_work=0`, `overall_status=RELEASED`, `selected_work=candidate-fd04772a23c5`를 보여준다. 이 후보는 이미 완료된 후보이므로 다음 세션이 착수하면 중복 작업이 된다.

**Independent Test**: 모든 macro 후보와 기존 후보가 released 또는 suppressed일 때 자율 작업 실행 보고서의 `selected_work.status`가 `EXECUTION_READY`이고 후보 ID가 frontier discovery 후보이면 검증된다.

**Acceptance Scenarios**:

1. **Given** 일반 후보 큐가 모두 closed 상태이고 기존 macro 후보가 모두 released됨, **When** 자율 작업 실행 루프가 보고서를 발행함, **Then** `selected_work`는 닫힌 후보가 아니라 `candidate-autonomous-frontier-discovery`가 된다.
2. **Given** 실행 가능한 일반 후보가 하나 이상 있음, **When** 같은 루프가 실행됨, **Then** frontier 후보는 끼어들지 않고 기존 실행 가능한 후보가 선택된다.

---

### User Story 2 - 고갈 원인과 다음 행동을 재현 가능하게 남기기 (Priority: P2)

운영자는 frontier 후보가 단순 "할 일 없음" 문구가 아니라, 닫힌 후보 수, released 수, suppressed 수, 목적 함수 학습 지표, 필요한 입력을 함께 남겨 다음 세션이 바로 스펙화할 수 있기를 원한다.

**Why this priority**: 후보 고갈은 실패가 아니라 자율 루프가 다음 탐색 축을 요구한다는 신호다. 근거가 없으면 다음 세션은 다시 sidecar를 조사해야 한다.

**Independent Test**: frontier 후보의 reason, next action, required inputs, source refs가 released-work, autonomous-work objective, pipeline-liveness, capital-path-readiness 근거를 포함하면 검증된다.

**Acceptance Scenarios**:

1. **Given** frontier 후보가 발행됨, **When** JSON 보고서를 읽음, **Then** 닫힌 후보 집계와 "다음 frontier 발굴" 행동이 한글 reason/next action에 표시된다.
2. **Given** Markdown 보고서를 읽음, **When** 운영자가 다음 작업을 고름, **Then** 닫힌 released 후보와 frontier 후보를 구분할 수 있다.

---

### User Story 3 - 안전 경계와 완료 장부를 보존하기 (Priority: P3)

운영자는 frontier 후보 발굴이 다음 세션 행동을 개선하되 돈 경로, 주문, 자본, live 전략, 허용 종목, 헌법, 커널, 비밀값을 건드리지 않기를 원한다.

**Why this priority**: 이 변경은 다음 자율 작업 선택 표면을 바꾸는 등급 2 운영 자동화 보정이다. 안전 경계가 넓어지면 안 된다.

**Independent Test**: released-work가 `candidate-autonomous-frontier-discovery` 완료 마커를 읽고, PR 본문과 HANDOFF가 위험 등급 2 및 안전 경계 불변을 기록하면 검증된다.

**Acceptance Scenarios**:

1. **Given** 스펙 092 tasks가 완료됨, **When** released-work 장부가 저장소를 스캔함, **Then** `candidate-autonomous-frontier-discovery`를 완료 후보로 기록한다.
2. **Given** 전체 검증을 수행함, **When** 안전 경계를 확인함, **Then** 주문·브로커·자본·live 전략·허용 종목·비밀값·외부 유료 서비스 변경은 없다.

### Edge Cases

- 모든 sidecar가 missing이면 기존 liveness repair 후보가 우선되어야 한다.
- operator approval 또는 blocked 후보가 있으면 frontier 후보가 안전 게이트를 가리지 않아야 한다.
- 아직 unreleased macro 후보가 있으면 기존 macro 후보 순서를 그대로 따라야 한다.
- frontier 후보 자체가 released-work에 들어간 뒤에는 같은 후보가 다시 선택되지 않아야 한다.
- 이 기능은 돈 경로 상태를 바꾸지 않는다. `PREVIEW_ONLY`는 그대로 유지된다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST emit an execution-ready frontier discovery candidate when all regular and existing macro candidates are closed and no executable, blocked, or operator-approval candidate remains.
- **FR-002**: System MUST NOT emit the frontier discovery candidate when a regular execution-ready candidate exists.
- **FR-003**: System MUST NOT mask operator-approval or blocked candidates with the frontier discovery candidate.
- **FR-004**: System MUST preserve the existing macro candidate order before frontier discovery.
- **FR-005**: Frontier discovery candidate MUST include closed, released, and suppressed candidate counts in the Korean reason.
- **FR-006**: Frontier discovery candidate MUST include required inputs from released-work, pipeline-liveness, capital-path-readiness, and autonomous-work evidence surfaces.
- **FR-007**: Autonomous work report MUST no longer present a closed released candidate as the selected work when frontier discovery can be emitted.
- **FR-008**: System MUST publish a completed candidate marker for `candidate-autonomous-frontier-discovery` only after Speckit tasks are complete.
- **FR-009**: System MUST preserve the existing safety boundary: no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel change, and no external paid service.
- **FR-010**: System MUST verify focused behavior, latest sidecar replay, released-work reproduction, full tests, lint, HANDOFF fact check, strict harness, and PR quality gate before merge.

### Key Entities *(include if feature involves data)*

- **Frontier Discovery Candidate**: `candidate-autonomous-frontier-discovery`, the execution-ready operating task emitted after known queues are exhausted.
- **Closed Queue Summary**: Counts of closed, released, and suppressed candidates used to explain why frontier discovery is needed.
- **Released Work Ledger**: The completion ledger that prevents already completed candidates from being selected again.
- **Autonomous Work Report**: The sidecar report that exposes `selected_work`, `ranked_work`, `suppressed_work`, objective calibration, and safety invariants.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Focused unit test shows all released macro candidates advance to `candidate-autonomous-frontier-discovery`.
- **SC-002**: Focused unit test shows regular execution-ready candidates still outrank frontier discovery.
- **SC-003**: Focused unit test shows operator-approval candidates are not masked.
- **SC-004**: Latest sidecar replay with repo-root released-work override selects the frontier discovery candidate instead of a closed released candidate.
- **SC-005**: `released_work_probe.py --repo-root .` includes `candidate-autonomous-frontier-discovery` after tasks are complete.
- **SC-006**: Full pytest, ruff, diff check, HANDOFF fact check, strict harness, and PR quality gate pass.
- **SC-007**: Final handoff records that this is a grade 2 operating automation correction, not a money-path or safety-perimeter change.

## Assumptions

- Existing macro candidates from specs 088, 089, and 091 remain valid and should keep their current order.
- The safest next step is to emit one deterministic frontier discovery candidate, not to invent multiple new domain candidates in the same change.
- Frontier discovery is an operating-system task for Codex, not a live trading action.
