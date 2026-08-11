# Tasks: Broad Validation Failure Frontier

**Input**: Design documents from `specs/126-broad-validation-failure-frontier/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/126-broad-validation-failure-frontier/`
- [x] T002 Update active feature pointer in `.specify/feature.json`
- [x] T003 Update active plan pointer in `CLAUDE.md`

---

## Phase 2: Foundational

**Purpose**: Prove the old wait path is no longer acceptable before completing the implementation.

- [x] T004 [P] Update parent-release regression expectations in `tests/unit/test_autonomous_work_execution.py`
- [x] T005 [P] Add next-entry regression expectations in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 검증 실패 parent 뒤에 기다리지 않고 전진한다 (Priority: P1)

**Goal**: Emit the first concrete validation-failure child packet after the parent candidate is released.

**Independent Test**: Focused autonomous-work tests select `candidate-broad-validation-failure-command-replay-contract`.

- [x] T006 [US1] Add validation-failure child candidate ids in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T007 [US1] Add child packet selection after broad validation-failure parent release in `src/auto_invest/analytics/autonomous_work_execution.py`

---

## Phase 4: User Story 2 - 실패를 여러 관점의 frontier 지도로 분리한다 (Priority: P2)

**Goal**: Render a deterministic validation-failure frontier map in JSON and Markdown.

**Independent Test**: Focused tests inspect `broad_validation_failure_frontier_map` and Markdown rendering.

- [x] T008 [US2] Add validation-failure frontier templates and map entries in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T009 [US2] Include validation-failure map in report JSON and Markdown in `src/auto_invest/analytics/autonomous_work_execution.py`

---

## Phase 5: User Story 3 - 돈 안전 경계는 넓히지 않는다 (Priority: P3)

**Goal**: Preserve no-live safety wording on every emitted child packet.

**Independent Test**: Focused tests inspect safety boundary and blocked package refs.

- [x] T010 [US3] Keep blocked package refs and validation groups on child packets
- [x] T011 [US3] Keep no-live safety boundary on child packets

---

## Phase 6: Validation, PR, and Handoff

- [x] T012 Run focused pytest for autonomous-work tests
- [x] T013 Run current sidecar replay from `quickstart.md`
- [x] T014 Run `uv run pytest`
- [x] T015 Run `uv run ruff check src tests`
- [x] T016 Run `git diff --check`
- [x] T017 Run `uv run python scripts/check_handoff_facts.py`
- [x] T018 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T019 Prepare PR body, PR quality gate evidence, release replay evidence, and HANDOFF refresh

## Dependencies & Execution Order

1. Phase 1 records the operating change.
2. Phase 2 locks the regression expectation.
3. User Story 1 changes selection behavior.
4. User Story 2 exposes the breadth map.
5. User Story 3 preserves safety boundary.
6. Phase 6 validates, opens PR, merges, and refreshes handoff if needed.

## Implementation Strategy

Implement the smallest autonomous-work extension that removes the passive wait loop. Keep it no-live, read-only, deterministic, and released-work driven.
