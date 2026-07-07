# Feature Specification: Execution Cost Basis Contract

**Feature Branch**: `Codex/104-execution-cost-basis-contract`
**Created**: 2026-07-07
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-execution-cost-basis-contract`를 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 체결 비용 기준 충분성을 분리한다 (Priority: P1)

운영자는 `execution-quality`와 `money-path` 증거를 손으로 다시 읽지 않고도, accepted/fill 비용 기준이 실제로 충분한지, 아니면 정상적인 관측 대기인지 구조화된 계약 보고서로 본다.

**Why this priority**: 스펙 102와 103은 체결 품질 frontier를 열고 브로커 거부 분류를 닫았다. 다음 후보는 비용 차감 엣지 판단이 실제 체결 비용 기준을 갖췄는지 분리해야 한다. 현재 증거에는 rejected order와 KIS smoke는 있으나 accepted/fill 비용 기준은 없으므로, 이를 장애로 오판하거나 충분하다고 과신하지 않아야 한다.

**Independent Test**: `execution-quality.execution_cost_basis`에 accepted/fill 비용 기준이 완성된 입력이면 `CONTRACT_READY`, 현재처럼 비용 기준 블록이 없으면 `OBSERVATION_WAIT`가 된다.

**Acceptance Scenarios**:

1. **Given** `execution-quality`에 `execution_cost_basis.basis_complete=true`와 accepted/fill 수, 측정 가능한 fill 수가 있음, **When** 보고서를 생성하면, **Then** 보고서는 `CONTRACT_READY`와 비용 기준 완료 요약을 제공한다.
2. **Given** `execution-quality`는 parse 가능하지만 `execution_cost_basis` 블록이 없음, **When** 보고서를 생성하면, **Then** 보고서는 `OBSERVATION_WAIT`로 두고 "실제 체결 비용 기준 관측 대기"라고 설명한다.

---

### User Story 2 - money-path 문맥과 안전 경계를 보존한다 (Priority: P2)

운영자는 비용 기준 판단이 실주문 재시도, live 설정 변경, 자본 배분과 연결되지 않는다는 사실을 보고서에서 확인한다.

**Why this priority**: accepted/fill 비용 기준은 돈 경로와 가까운 증거다. 읽기 전용 계약이 실거래 전환이나 주문 재시도를 암시하면 안전 경계가 흐려진다.

**Independent Test**: `money-path`가 `PREVIEW_ONLY`이고 accepted/fill 수가 0이면 보고서는 money-path 문맥을 PASS로 읽되 비용 기준은 WAIT로 둔다.

**Acceptance Scenarios**:

1. **Given** `money-path.live_money_state.status=PREVIEW_ONLY`, **When** 보고서를 생성하면, **Then** 보고서는 실주문 가능 상태가 아니며 새 표본을 강제로 만들지 않는다고 남긴다.
2. **Given** `money-path` 입력이 없거나 malformed임, **When** 보고서를 생성하면, **Then** overall status는 `BLOCKED`이고 결손 입력이 evidence surface와 gate에 남는다.

---

### User Story 3 - 완료 후보를 닫고 다음 체결 품질 후보로 전진한다 (Priority: P3)

운영자는 `candidate-execution-cost-basis-contract`가 완료 처리된 뒤 같은 후보를 다시 받지 않고, 다음 체결 품질 후보인 `candidate-broker-diagnostic-liveness-contract`로 전진한 자율 work packet을 받는다.

**Why this priority**: 계약 보고서만 만들어도 released-work 완료 마커가 없으면 자율 루프는 같은 후보를 반복 선택한다. 스펙 102의 체결 품질 frontier 순서를 실제로 소비해야 한다.

**Independent Test**: released-work가 `candidate-execution-cost-basis-contract` 완료를 읽으면 autonomous-work selected_work가 `candidate-broker-diagnostic-liveness-contract`로 전진하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 브로커 거부 분류와 체결 비용 기준 후보가 released-work에 있음, **When** autonomous-work 보고서를 생성하면, **Then** selected_work는 `candidate-broker-diagnostic-liveness-contract`이고 체결 비용 기준 row는 released 상태다.
2. **Given** 체결 비용 기준 후보만 완료되고 브로커 진단 생존성 후보는 미완료임, **When** 보고서를 생성하면, **Then** 브로커 진단 생존성 후보는 open 상태로 유지된다.

### Edge Cases

- `execution-quality`는 parse 가능하지만 `execution_cost_basis`가 없으면 실패가 아니라 관측 대기로 둔다.
- accepted/fill 수는 있으나 측정 가능한 비용 기준이 없으면 `CONTRACT_READY`로 과장하지 않는다.
- `money-path`가 `PREVIEW_ONLY`이면 새 accepted/fill 표본을 만들기 위해 실주문을 시도하지 않는다.
- 필수 sidecar가 없거나 malformed이면 `BLOCKED`로 두고 결손 입력을 명시한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a deterministic execution cost basis report from existing sidecar snapshots only.
- **FR-002**: System MUST consume `automation/execution-quality-last-run:LAST_RUN.md`, `automation/kis-smoke-last-run:LAST_RUN.md`, `automation/rebalance-micro-gtaa-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, and `automation/capital-path-readiness-last-run:capital_path_readiness.json`.
- **FR-003**: System MUST distinguish `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED` from quality gates rather than free text.
- **FR-004**: System MUST require measurable accepted/fill cost basis before reporting `CONTRACT_READY`.
- **FR-005**: System MUST treat missing `execution_cost_basis` evidence as observation wait when required inputs are otherwise parseable.
- **FR-006**: System MUST include `completed_candidate_id: candidate-execution-cost-basis-contract` and `next_candidate_id: candidate-broker-diagnostic-liveness-contract`.
- **FR-007**: System MUST preserve autonomous-work ordering so released execution cost basis advances to `candidate-broker-diagnostic-liveness-contract`.
- **FR-008**: System MUST include safety invariants showing no broker API call, no orders, no capital allocation, no live strategy change, no whitelist/caps change, no secret read/write, no constitution/kernel modification, no fresh external collection, and no external paid service.
- **FR-009**: System MUST NOT infer cost adequacy from rejected-order rows or `PREVIEW_ONLY` money-path state.

### Key Entities *(include if feature involves data)*

- **Execution Cost Basis Report**: The read-only report containing overall status, evidence surfaces, execution-quality summary, money-path summary, cost basis summary, quality gates, completion marker, next candidate, and safety boundary.
- **Cost Basis Summary**: The normalized status of accepted/fill cost basis, including whether `execution_cost_basis` exists, accepted/fill count, measurable fill count, turnover observation, and live-money context.
- **Quality Gate**: A PASS/WAIT/FAIL condition for parseability, cost-basis observability, accepted/fill cost basis, money-path context, and safety boundary.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-execution-cost-basis-contract`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With ready `execution_cost_basis` evidence, the report returns `CONTRACT_READY` and `cost_basis_state=COST_BASIS_READY`.
- **SC-002**: With current evidence lacking `execution_cost_basis`, the report returns `OBSERVATION_WAIT` and does not suggest order retry, capital change, or live strategy change.
- **SC-003**: Missing or malformed `execution-quality` or `money-path` evidence returns `BLOCKED` with a failing parse/context gate.
- **SC-004**: Report JSON includes `completed_candidate_id` and `next_candidate_id`, and Markdown includes `## 비용 기준 요약`.
- **SC-005**: Focused unit and integration tests for the new probe and autonomous-work advancement pass.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- Current remote evidence has no accepted/fill cost basis block, so the expected live classification is observation wait, not a blocker.
- `money-path` `PREVIEW_ONLY` means the system should not attempt real orders to create new samples.
- This feature emits local/probe reports and SDD completion markers; it does not add a new scheduled workflow unless a later automation task explicitly decides to publish the report.

completed_candidate_id: candidate-execution-cost-basis-contract
