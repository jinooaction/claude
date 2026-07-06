# Tasks: Cost-Adjusted Edge Experiment

**Input**: Design documents from `specs/097-cost-adjusted-edge-experiment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/097-cost-adjusted-edge-experiment/`

---

## Phase 2: Foundational

**Purpose**: Establish the no-live cost-adjusted report contract before implementation.

- [x] T003 [P] Add failing core report tests in `tests/unit/test_cost_adjusted_edge_experiment.py`
- [x] T004 [P] Add failing probe manifest/output tests in `tests/integration/test_cost_adjusted_edge_experiment_probe.py`

---

## Phase 3: User Story 1 - 비용 차감 실험 계약을 한 곳에서 본다 (Priority: P1)

**Goal**: Emit a deterministic JSON/Markdown contract for the selected work packet.

**Independent Test**: Focused tests show stable experiment id, required inputs, execution-cost summary, cost-stressed candidates, and safety boundary.

- [x] T005 [US1] Implement report data model and builder in `src/auto_invest/analytics/cost_adjusted_edge_experiment.py`
- [x] T006 [US1] Implement probe manifest and sidecar reader in `scripts/cost_adjusted_edge_experiment_probe.py`
- [x] T007 [US1] Render JSON and Markdown report outputs

---

## Phase 4: User Story 2 - 관측 부족과 비용 기준 부족을 정직하게 분리한다 (Priority: P2)

**Goal**: Report forward observation wait, execution-quality status, cost-basis completeness, and blockers without declaring false live readiness.

**Independent Test**: Current-style insufficient observations and incomplete cost basis remain visible as wait; critical liveness failure produces `BLOCKED`.

- [x] T008 [US2] Parse forward tracks into cost-stress candidates
- [x] T009 [US2] Parse execution-quality Markdown decision JSON into `ExecutionCostSnapshot`
- [x] T010 [US2] Add validation gates for execution-quality, cost-basis completeness, forward observation readiness, and no-live safety

---

## Phase 5: User Story 3 - 후보 완료 뒤 다음 자율 루프가 전진한다 (Priority: P3)

**Goal**: Close only `candidate-cost-adjusted-edge-experiment` and prove autonomous-work advances.

**Independent Test**: released-work scan includes the completed candidate, then autonomous-work local replay does not select `candidate-cost-adjusted-edge-experiment`.

- [x] T011 [US3] Add completion marker contract for `candidate-cost-adjusted-edge-experiment`
- [x] T012 [US3] Run released-work and autonomous-work local replay from `quickstart.md`

---

## Phase 6: Validation, PR, and Handoff

- [x] T013 Run focused pytest for new unit and integration tests
- [x] T014 Run local sidecar replay from `quickstart.md`
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 creates the contract report.
3. User Story 2 separates observation, execution, and cost-basis waits.
4. User Story 3 closes this candidate and verifies next-candidate movement.
5. Phase 6 completes verification, PR, merge, deployment observation, and handoff refresh.

## Implementation Strategy

Implement MVP first: deterministic report plus probe, then add cost stress metrics and blocker/wait gates, then prove released-work closure advances the autonomous frontier. Keep all changes read-only and use existing SDD, PR, and handoff gates.
