# Feature Specification: Execution Quality Frontier Map

**Feature Branch**: `Codex/102-execution-quality-frontier-map`
**Created**: 2026-07-07
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-execution-quality-frontier-map`을 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 체결 품질 안쪽 후보 공간을 본다 (Priority: P1)

운영자는 거시 후보 지도에서 "체결 품질"이 선택된 뒤, 주문 거부, 브로커 진단, 의도 손실, 비용 관측 중 어떤 읽기 전용 체결 품질 후보가 다음으로 실행 가능한지 구조화된 지도를 받는다.

**Why this priority**: 스펙 101은 데이터 증거 후보를 모두 닫은 뒤 `candidate-execution-quality-frontier-map`으로 전진시켰지만, 체결 품질 영역 안쪽 후보를 만들지 않으면 다음 세션이 `execution-quality`, `kis-smoke`, `rebalance-micro-gtaa` 증거를 다시 손으로 조합해야 한다.

**Independent Test**: 스펙 101까지 released-work로 닫힌 입력에서 autonomous-work 보고서가 `execution_quality_frontier_map`을 JSON과 Markdown에 발행하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 투자 엣지와 데이터 증거 후보가 released-work로 완료 처리된 상태, **When** autonomous-work 실행 보고서를 생성하면, **Then** 보고서는 체결 품질 frontier 지도와 첫 체결 품질 후보를 함께 보여준다.
2. **Given** `execution-quality`, `kis-smoke`, `rebalance-micro-gtaa`, `money-path`, `pipeline-liveness`, `released-work`, `capital-path-readiness` sidecar가 존재하는 상태, **When** 보고서를 생성하면, **Then** 그 증거들이 체결 품질 후보의 required input에 남는다.

---

### User Story 2 - 체결 품질 frontier 후보 완료 뒤 첫 진단 후보로 전진한다 (Priority: P2)

운영자는 `candidate-execution-quality-frontier-map`이 완료 처리된 뒤 같은 후보를 다시 받지 않고, 거부 주문과 브로커 오류를 더 좁은 계약으로 닫는 구체적 체결 품질 후보를 받는다.

**Why this priority**: 완료된 frontier 후보가 반복 선택되면 자율 성장 루프가 다시 수동 후보 발굴 상태로 돌아간다. 이번 작업은 체결 품질 후보 발굴을 실제 진단 계약 후보로 분해해야 한다.

**Independent Test**: released-work에 `candidate-execution-quality-frontier-map`을 넣으면 selected_work가 `candidate-broker-rejection-taxonomy-contract`로 바뀌는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `candidate-execution-quality-frontier-map`이 released-work에 있음, **When** 보고서를 생성하면, **Then** selected_work는 `candidate-broker-rejection-taxonomy-contract`이고 상태는 `EXECUTION_READY`다.
2. **Given** 첫 체결 품질 후보도 released-work에 있음, **When** 보고서를 생성하면, **Then** 체결 품질 지도는 다음 미완료 체결 품질 후보로 넘어가거나 더 이상 없으면 다음 거시 영역 후보로 넘어간다.

---

### User Story 3 - 안전 경계와 기존 우선순위를 보존한다 (Priority: P3)

운영자는 체결 품질 후보를 생성하더라도 새 브로커 호출, 주문, 자본 배분, live 전략, 허용 종목, 비밀값, 헌법·커널이 변하지 않는다는 것을 확인할 수 있다.

**Why this priority**: 체결 품질은 실제 돈 경로와 가까운 증거지만, 이번 변경은 이미 발행된 sidecar를 읽어 work packet을 만드는 보고서 확장만 해야 한다.

**Independent Test**: 일반 실행 후보, 운영자 승인 후보, blocked/repair 후보가 있을 때 체결 품질 재생성 후보가 그것들을 가리지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 더 높은 우선순위의 일반 실행 후보가 있음, **When** 보고서를 생성하면, **Then** 그 일반 후보가 selected_work로 유지된다.
2. **Given** 안전 표면이 있는 후보가 있음, **When** 보고서를 생성하면, **Then** 운영자 승인 요구 상태가 유지되고 체결 품질 후보는 자동 착수하지 않는다.

### Edge Cases

- 체결 품질 frontier 후보는 released됐지만 모든 체결 품질 후보도 released된 경우 다음 거시 영역 후보로 넘어간다.
- `execution-quality`, `kis-smoke`, 또는 `rebalance-micro-gtaa` sidecar가 없거나 깨진 경우에도 이번 루프는 주문·자본 변경 없이 증거 상태를 보고서에 남긴다.
- `released-work`가 아직 스펙 102 완료 마커를 읽지 못한 경우에는 `candidate-execution-quality-frontier-map`이 반복 선택될 수 있으므로 완료 마커 계약을 반드시 남긴다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add a deterministic `execution_quality_frontier_map` to the autonomous-work report JSON and Markdown.
- **FR-002**: System MUST include at least one execution-quality candidate with stable id `candidate-broker-rejection-taxonomy-contract`.
- **FR-003**: System MUST keep `candidate-execution-quality-frontier-map` selected until released-work records it as completed.
- **FR-004**: System MUST select the highest-priority unreleased execution-quality candidate after `candidate-execution-quality-frontier-map` is released.
- **FR-005**: System MUST include `automation/execution-quality-last-run:LAST_RUN.md`, `automation/kis-smoke-last-run:LAST_RUN.md`, `automation/rebalance-micro-gtaa-last-run:LAST_RUN.md`, `automation/money-path-last-run:LAST_RUN.md`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, and `automation/capital-path-readiness-last-run:capital_path_readiness.json` as required inputs for the first execution-quality candidate.
- **FR-006**: System MUST preserve existing priority ordering: repair, regular execution, operator approval, blocked, released, and suppressed packets cannot be masked by execution-quality regeneration.
- **FR-007**: System MUST mark this work's completed candidate as `candidate-execution-quality-frontier-map`.
- **FR-008**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Execution Quality Frontier Map**: A deterministic list of execution-quality areas, with priority, status, candidate id, rationale, next action, and required evidence refs.
- **Execution Quality Candidate**: A generated `WorkPacket` derived from the highest-priority unreleased execution-quality frontier entry.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-execution-quality-frontier-map`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With data-evidence candidates completed but spec 102 not released, selected_work remains `candidate-execution-quality-frontier-map`.
- **SC-002**: With spec 102 completed, selected_work advances to `candidate-broker-rejection-taxonomy-contract`.
- **SC-003**: Report JSON includes `execution_quality_frontier_map`, and Markdown includes `## 체결 품질 frontier 지도`.
- **SC-004**: Focused autonomous-work unit and integration tests pass.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-006**: Final handoff records that this is a grade 2 read-only operating automation change, not a money-path or safety-perimeter change.

## Assumptions

- `automation/execution-quality-last-run` is the current safe read-only execution-quality evidence package.
- `automation/kis-smoke-last-run` is the current safe read-only KIS broker connection diagnostic.
- `automation/rebalance-micro-gtaa-last-run` is the current safe read-only source for live gate and rejected-order opportunity diagnostics.
- `pipeline-liveness` remains the source of freshness status for execution-quality and broker-related sidecars.
- Execution-quality candidates are work packets for later SDD implementation; this feature does not perform broker calls, order retries, capital changes, or a new execution-quality probe itself.

