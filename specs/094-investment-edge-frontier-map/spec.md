# Feature Specification: Investment Edge Frontier Map

**Feature Branch**: `Codex/094-investment-edge-frontier-map`
**Created**: 2026-07-04
**Status**: Draft
**Input**: User description: "다음 자율 후보 `candidate-investment-edge-frontier-map`을 목표 스킬로 꼼꼼하게 완수"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 투자 엣지 안쪽 후보 공간을 본다 (Priority: P1)

운영자는 거시 후보 지도에서 "투자 엣지"가 선택된 뒤, 그 안쪽에서 어떤 no-live 실험 후보가 다음으로 실행 가능한지 구조화된 지도를 받는다.

**Why this priority**: 스펙 093은 투자 엣지 영역까지는 열었지만, 그 안쪽 실험 후보를 만들지 않으면 다시 수동 발굴이 필요하다.

**Independent Test**: 스펙 093까지 released-work로 닫힌 입력에서 autonomous-work 보고서가 `investment_edge_frontier_map`을 JSON과 Markdown에 발행하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 거시 후보 재생성 후보가 released-work로 완료 처리된 상태, **When** autonomous-work 실행 보고서를 생성하면, **Then** 보고서는 투자 엣지 frontier 지도와 첫 no-live 실험 후보를 함께 보여준다.
2. **Given** 투자 엣지 지도 입력 sidecar가 존재하는 상태, **When** 보고서를 생성하면, **Then** `rebalance-paper-forward`, `money-path`, `released-work`, `evolution-ledger`가 투자 엣지 후보의 required input에 남는다.

---

### User Story 2 - 투자 엣지 frontier 후보 완료 뒤 첫 no-live 실험 후보로 전진한다 (Priority: P2)

운영자는 `candidate-investment-edge-frontier-map`이 완료 처리된 뒤 같은 후보를 다시 받지 않고, forward verdict와 money-path 증거를 이용하는 구체적인 no-live 실험 후보를 받는다.

**Why this priority**: 완료된 후보를 반복하면 자율 성장 루프가 같은 질문을 다시 던진다. 이번 작업은 투자 성과 후보 발굴을 실제 실험 후보로 분해해야 한다.

**Independent Test**: released-work에 `candidate-investment-edge-frontier-map`을 넣으면 selected_work가 새 no-live 실험 후보로 바뀌는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `candidate-investment-edge-frontier-map`이 released-work에 있음, **When** 보고서를 생성하면, **Then** selected_work는 `candidate-forward-regime-edge-experiment`이고 상태는 `EXECUTION_READY`다.
2. **Given** 그 no-live 실험 후보도 released-work에 있음, **When** 보고서를 생성하면, **Then** 투자 엣지 지도는 다음 미완료 실험 후보로 넘어가거나 더 이상 없으면 다음 거시 영역 후보로 넘어간다.

---

### User Story 3 - 안전 경계와 기존 우선순위를 보존한다 (Priority: P3)

운영자는 투자 엣지 후보를 생성하더라도 돈 경로, 주문, live 전략, 허용 종목, 비밀값, 헌법·커널이 변하지 않는다는 것을 확인할 수 있다.

**Why this priority**: "투자 엣지"는 돈 경로와 가까운 말이지만, 이번 변경은 no-live 후보 생성과 보고서 확장만 해야 한다.

**Independent Test**: 일반 실행 후보, 운영자 승인 후보, blocked/repair 후보가 있을 때 투자 엣지 재생성 후보가 그것들을 가리지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 더 높은 우선순위의 일반 실행 후보가 있음, **When** 보고서를 생성하면, **Then** 그 일반 후보가 selected_work로 유지된다.
2. **Given** 안전 표면이 있는 후보가 있음, **When** 보고서를 생성하면, **Then** 운영자 승인 요구 상태가 유지되고 투자 엣지 후보는 자동 착수하지 않는다.

### Edge Cases

- 투자 엣지 frontier 후보는 released됐지만 모든 투자 엣지 no-live 실험 후보도 released된 경우 다음 거시 영역 후보로 넘어간다.
- 투자 엣지 입력 sidecar가 없거나 깨진 경우에도 이번 루프는 주문·자본 변경 없이 증거 상태를 보고서에 남긴다.
- `released-work`가 아직 스펙 094 완료 마커를 읽지 못한 경우에는 `candidate-investment-edge-frontier-map`이 반복 선택될 수 있으므로 완료 마커 계약을 반드시 남긴다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add a deterministic `investment_edge_frontier_map` to the autonomous-work report JSON and Markdown.
- **FR-002**: System MUST include at least one no-live investment-edge experiment candidate with stable id `candidate-forward-regime-edge-experiment`.
- **FR-003**: System MUST keep `candidate-investment-edge-frontier-map` selected until released-work records it as completed.
- **FR-004**: System MUST select the highest-priority unreleased investment-edge no-live experiment candidate after `candidate-investment-edge-frontier-map` is released.
- **FR-005**: System MUST include `rebalance-paper-forward`, `money-path`, `released-work`, `evolution-ledger`, and `pipeline-liveness` as required inputs for investment-edge no-live experiment candidates.
- **FR-006**: System MUST preserve existing priority ordering: repair, regular execution, operator approval, blocked, released, and suppressed packets cannot be masked by investment-edge regeneration.
- **FR-007**: System MUST mark this work's completed candidate as `candidate-investment-edge-frontier-map`.
- **FR-008**: System MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read/write secrets, modify constitution/kernel files, or invoke paid external services.

### Key Entities *(include if feature involves data)*

- **Investment Edge Frontier Map**: A deterministic list of no-live investment experiment areas, with priority, status, candidate id, rationale, next action, and required evidence refs.
- **Investment Edge Experiment Candidate**: A generated `WorkPacket` derived from the highest-priority unreleased investment edge frontier entry.
- **Completed Candidate Marker**: The released-work-readable value `completed_candidate_id: candidate-investment-edge-frontier-map`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With spec 093 completed but spec 094 not released, selected_work remains `candidate-investment-edge-frontier-map`.
- **SC-002**: With spec 094 completed, selected_work advances to `candidate-forward-regime-edge-experiment`.
- **SC-003**: Report JSON includes `investment_edge_frontier_map`, and Markdown includes `## 투자 엣지 frontier 지도`.
- **SC-004**: Focused autonomous-work unit and integration tests pass.
- **SC-005**: Full `uv run pytest`, `uv run ruff check src tests`, `check_handoff_facts.py`, strict agent harness, and PR quality gate pass before merge.
- **SC-006**: Final handoff records that this is a grade 2 read-only operating automation change, not a money-path or safety-perimeter change.

## Assumptions

- `rebalance-paper-forward` is the current forward-verdict evidence surface for no-live paper tournament outcomes.
- `money-path` remains the authoritative top-level money state surface and currently reports `PREVIEW_ONLY`.
- Investment-edge experiment candidates are work packets for later SDD implementation; this feature does not run a new investment experiment itself.
- The first concrete no-live experiment should test regime-conditioned forward edge because existing forward verdict, regime scoring, and money-path evidence are already in the repository.
