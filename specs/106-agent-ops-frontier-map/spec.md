# Feature Specification: Agent Ops Frontier Map

**Feature Branch**: `Codex/106-agent-ops-frontier-map`
**Created**: 2026-07-08
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-agent-ops-frontier-map`을 목표 스킬로 꼼꼼하게 진행"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 운영 체계 안쪽 후보 공간을 본다 (Priority: P1)

운영자는 거시 후보 지도에서 "운영 체계"가 선택된 뒤, handoff 사실성, PR/merge 증거, worktree 동시 작업 방어 중 어떤 운영 체계 후보가 다음으로 실행 가능한지 구조화된 지도를 받는다.

**Why this priority**: 스펙 105는 체결 품질 frontier의 마지막 열린 후보를 닫고 `candidate-agent-ops-frontier-map`으로 전진했다. 운영 체계 후보 지도가 없으면 다음 세션은 handoff, harness, PR 품질 관문, 동시 작업 방어 증거를 다시 손으로 조합해야 한다.

**Independent Test**: 스펙 105까지 released-work로 닫힌 입력에서 autonomous-work 보고서가 `agent_ops_frontier_map`을 JSON과 Markdown에 발행하고 첫 운영 체계 후보를 설명하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 체결 품질 frontier 후보가 모두 released-work에 있음, **When** autonomous-work 실행 보고서를 생성하면, **Then** 보고서는 운영 체계 frontier 지도와 `candidate-agent-ops-frontier-map`을 함께 보여준다.
2. **Given** 보고서를 Markdown으로 렌더링하면, **When** 다음 세션이 읽을 때, **Then** `## 운영 체계 frontier 지도` 표에서 추천 후보와 이유를 확인할 수 있다.

---

### User Story 2 - 완료 뒤 첫 운영 체계 후보로 전진한다 (Priority: P2)

운영자는 `candidate-agent-ops-frontier-map`이 완료 처리된 뒤 같은 후보를 다시 받지 않고, handoff 사실성 생존성 계약 같은 더 좁은 운영 체계 후보를 받는다.

**Why this priority**: frontier 지도 후보가 완료됐는데도 반복 선택되면 자율 루프는 다시 운영자에게 다음 후보 발굴을 요구한다. 이번 작업은 운영 체계 영역 안쪽 후보를 실제 다음 work packet으로 분해해야 한다.

**Independent Test**: released-work에 `candidate-agent-ops-frontier-map`을 넣으면 selected_work가 `candidate-handoff-truth-liveness-contract`로 바뀌는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `candidate-agent-ops-frontier-map`이 released-work에 있음, **When** 보고서를 생성하면, **Then** selected_work는 `candidate-handoff-truth-liveness-contract`이고 상태는 `EXECUTION_READY`다.
2. **Given** 첫 운영 체계 후보도 released-work에 있음, **When** 보고서를 생성하면, **Then** 운영 체계 지도는 다음 미완료 운영 후보로 넘어간다.

---

### User Story 3 - 안전 경계와 기존 우선순위를 보존한다 (Priority: P3)

운영자는 운영 체계 후보를 생성하더라도 새 브로커 호출, 주문, 자본 배분, live 전략, 허용 종목, 비밀값, 헌법·커널이 변하지 않는다는 것을 확인할 수 있다.

**Why this priority**: 운영 체계 후보 생성은 에이전트 행동 표면에 영향을 주므로 안전 경계와 기존 복구/승인 후보 우선순위를 보존해야 한다.

**Independent Test**: 일반 실행 후보, 운영자 승인 후보, blocked/repair 후보가 있을 때 운영 체계 재생성 후보가 그것들을 가리지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 더 높은 우선순위의 일반 실행 후보가 있음, **When** 보고서를 생성하면, **Then** 그 일반 후보가 selected_work로 유지된다.
2. **Given** 안전 표면이 있는 후보가 있음, **When** 보고서를 생성하면, **Then** 운영자 승인 요구 상태가 유지되고 운영 체계 후보는 자동 착수하지 않는다.

### Edge Cases

- `candidate-agent-ops-frontier-map`이 아직 released-work에 없으면 같은 후보가 selected_work로 남아야 한다.
- 운영 체계 하위 후보가 모두 released되면 다음 후보를 반복하지 않고 closed 상태를 명확히 보여야 한다.
- 모든 sidecar가 없거나 pipeline-liveness가 critical이면 기존 복구 후보가 우선한다.
- 운영 체계 후보는 위험 등급 2, 안전 표면 없음인 읽기 전용 후보로만 생성된다.
- handoff와 harness 증거는 작업 입력으로 참조하지만 이 보고서가 직접 PR을 만들거나 merge하지 않는다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add a deterministic `agent_ops_frontier_map` to the autonomous-work report JSON and Markdown.
- **FR-002**: System MUST include stable operating-system candidate ids for handoff truth liveness, PR/merge evidence liveness, and worktree concurrency liveness.
- **FR-003**: System MUST keep `candidate-agent-ops-frontier-map` selected until released-work records it as completed.
- **FR-004**: System MUST select the highest-priority unreleased operating-system candidate after `candidate-agent-ops-frontier-map` is released.
- **FR-005**: System MUST include `automation/autonomous-work-execution-last-run:LAST_RUN.md`, `automation/released-work-last-run:released_work.json`, `automation/pipeline-liveness-last-run:LAST_RUN.md`, `HANDOFF.md`, `scripts/check_handoff_facts.py`, `scripts/agent_harness_probe.py`, and `.github/workflows/pr-quality-gate.yml` as required inputs for generated operating-system candidates.
- **FR-006**: System MUST preserve existing priority ordering: repair, regular execution, operator approval, blocked, released, and suppressed packets cannot be masked by agent-ops regeneration.
- **FR-007**: System MUST mark this work's completed candidate as `candidate-agent-ops-frontier-map`.
- **FR-008**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Agent Ops Frontier Map**: A deterministic list of operating-system candidate areas, with priority, status, candidate id, rationale, next action, and required evidence refs.
- **Agent Ops Candidate**: A generated `WorkPacket` derived from the highest-priority unreleased operating-system frontier entry.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-agent-ops-frontier-map`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With broker diagnostic liveness completed but spec 106 not released, selected_work remains `candidate-agent-ops-frontier-map`.
- **SC-002**: With spec 106 completed, selected_work advances to `candidate-handoff-truth-liveness-contract`.
- **SC-003**: Report JSON includes `agent_ops_frontier_map`, and Markdown includes `## 운영 체계 frontier 지도`.
- **SC-004**: Focused autonomous-work unit and integration tests pass.
- **SC-005**: Local released-work and autonomous-work replay confirm the completion marker is detected and the next candidate is selected.
- **SC-006**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.

## Assumptions

- The correct implementation surface is the existing read-only autonomous-work execution report, not a new workflow that opens PRs or writes code automatically.
- Operating-system candidates are work packets for later SDD implementation through the existing PR, validation, merge, and HANDOFF path.
- The first operating-system frontier candidate should target handoff truth liveness because stale handoff state repeatedly causes duplicated discovery work.
- The change is risk grade 2 because it changes autonomous next-work selection/reporting, but it does not touch safety boundaries or money paths.

completed_candidate_id: candidate-agent-ops-frontier-map
next_candidate_id: candidate-handoff-truth-liveness-contract
