# Tasks: Execution Quality Frontier Map

**Input**: Design documents from `specs/102-execution-quality-frontier-map/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/102-execution-quality-frontier-map/`

---

## Phase 2: Foundational

**Purpose**: Establish the report and candidate contract before implementation.

- [x] T003 [P] Add failing report contract coverage for `execution_quality_frontier_map` JSON/Markdown in `tests/unit/test_autonomous_work_execution.py`
- [x] T004 [P] Add failing probe manifest coverage for execution-quality sidecar inputs in `tests/integration/test_autonomous_work_execution_probe.py`

---

## Phase 3: User Story 1 - 체결 품질 안쪽 후보 공간을 본다 (Priority: P1)

**Goal**: Autonomous-work report exposes a deterministic execution quality frontier map.

**Independent Test**: Focused unit and integration tests show the map in JSON/Markdown and manifest refs.

- [x] T005 [US1] Add execution-quality evidence source refs and report data model in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T006 [US1] Add `execution-quality`, `kis-smoke`, and `rebalance-micro-gtaa` to `scripts/autonomous_work_execution_probe.py`
- [x] T007 [US1] Render `execution_quality_frontier_map` in Markdown and JSON

---

## Phase 4: User Story 2 - 완료 뒤 첫 체결 품질 후보로 전진한다 (Priority: P2)

**Goal**: Released `candidate-execution-quality-frontier-map` advances to `candidate-broker-rejection-taxonomy-contract`.

**Independent Test**: Focused unit test changes released-work input and observes selected_work transition.

- [x] T008 [US2] Add transition test for released execution-quality frontier candidate in `tests/unit/test_autonomous_work_execution.py`
- [x] T009 [US2] Implement nested execution-quality candidate selection in `src/auto_invest/analytics/autonomous_work_execution.py`
- [x] T010 [US2] Add completion marker contract for `candidate-execution-quality-frontier-map`

---

## Phase 5: User Story 3 - 안전 경계와 기존 우선순위를 보존한다 (Priority: P3)

**Goal**: Generated execution-quality candidates remain read-only and do not mask higher-priority work.

**Independent Test**: Existing priority/safety tests pass plus focused assertions check risk grade and required inputs.

- [x] T011 [US3] Verify generated execution-quality candidate uses risk grade 2 and no safety impact
- [x] T012 [US3] Verify regular/operator/blocked priority behavior is preserved

---

## Phase 6: Validation, PR, and Handoff

- [x] T013 Run focused pytest for autonomous-work unit and integration tests
- [x] T014 Run local sidecar replay from `quickstart.md`
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 makes the map visible.
3. User Story 2 changes selection after released-work closes this feature.
4. User Story 3 preserves safety and priority behavior.
5. Phase 6 completes verification, merge, deployment observation, and handoff refresh.

## Implementation Strategy

Implement MVP first: expose `execution_quality_frontier_map`, then prove `candidate-execution-quality-frontier-map` advances to `candidate-broker-rejection-taxonomy-contract` only after released-work records this spec's completion marker. Keep all changes read-only and use existing SDD, PR, and handoff gates.
