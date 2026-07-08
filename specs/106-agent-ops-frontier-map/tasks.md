# Tasks: Agent Ops Frontier Map

**Input**: Design documents from `specs/106-agent-ops-frontier-map/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required because this changes autonomous work selection behavior.

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/106-agent-ops-frontier-map/`

---

## Phase 2: Foundational

**Purpose**: Establish the report and candidate contract before implementation.

- [x] T003 [P] Add failing report contract coverage for `agent_ops_frontier_map` JSON/Markdown in `tests/unit/test_autonomous_work_execution.py`
- [x] T004 [P] Add failing selection coverage for post-agent-ops frontier candidate advancement in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 운영 체계 안쪽 후보 공간을 본다 (Priority: P1)

**Goal**: Autonomous-work report exposes a deterministic agent-ops frontier map.

**Independent Test**: Focused unit tests show the map in JSON/Markdown and required input refs.

- [x] T005 [US1] Add agent-ops frontier templates, data model, and source refs in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T006 [US1] Render `agent_ops_frontier_map` in Markdown and JSON

---

## Phase 4: User Story 2 - 완료 뒤 첫 운영 체계 후보로 전진한다 (Priority: P2)

**Goal**: Released `candidate-agent-ops-frontier-map` advances to `candidate-handoff-truth-liveness-contract`.

**Independent Test**: Focused unit test changes released-work input and observes selected_work transition.

- [x] T007 [US2] Implement nested agent-ops candidate selection in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T008 [US2] Add completion marker contract for `candidate-agent-ops-frontier-map`

---

## Phase 5: User Story 3 - 안전 경계와 기존 우선순위를 보존한다 (Priority: P3)

**Goal**: Generated agent-ops candidates remain read-only and do not mask higher-priority work.

**Independent Test**: Existing priority/safety tests pass plus focused assertions check risk grade and required inputs.

- [x] T009 [US3] Verify generated agent-ops candidate uses risk grade 2 and no safety impact
- [x] T010 [US3] Verify regular/operator/blocked priority behavior is preserved

---

## Phase 6: Validation, PR, and Handoff

- [x] T011 Run focused pytest for autonomous-work unit and integration tests
- [x] T012 Run local sidecar replay from `quickstart.md`
- [x] T013 Run `uv run pytest`
- [x] T014 Run `uv run ruff check src tests`
- [x] T015 Run `git diff --check`
- [x] T016 Run `uv run python scripts/check_handoff_facts.py`
- [x] T017 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T018 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 makes the map visible.
3. User Story 2 changes selection after released-work closes this feature.
4. User Story 3 preserves safety and priority behavior.
5. Phase 6 completes verification, merge, deployment observation, and handoff refresh.

## Parallel Opportunities

- T002 can run independently of pointer updates.
- T003-T004 can be drafted together because they touch related assertions but different scenarios.
- T011 and T012 can run in parallel once implementation is complete.

## Implementation Strategy

Implement MVP first: expose `agent_ops_frontier_map`, then prove `candidate-agent-ops-frontier-map` advances to `candidate-handoff-truth-liveness-contract` only after released-work records this spec's completion marker. Keep all changes read-only and use existing SDD, PR, and handoff gates.
