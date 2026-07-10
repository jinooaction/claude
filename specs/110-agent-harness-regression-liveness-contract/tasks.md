# Tasks: Agent Harness Regression Liveness Contract

**Input**: Design documents from `specs/110-agent-harness-regression-liveness-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required because this changes operating-system evidence and autonomous next-work completion behavior.

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/110-agent-harness-regression-liveness-contract/`

---

## Phase 2: Foundational

**Purpose**: Establish contract expectations before implementation.

- [x] T003 [P] Add agent harness regression liveness unit tests in `tests/unit/test_agent_harness_regression_liveness.py`
- [x] T004 [P] Add probe integration coverage in `tests/integration/test_agent_harness_regression_liveness_probe.py`
- [x] T005 [P] Add autonomous-work completion transition coverage in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 하네스 회귀 방어가 살아 있는지 한 번에 본다 (Priority: P1)

**Goal**: A deterministic report exposes harness source surfaces, suite coverage, completion marker, next candidate, and safety boundary.

**Independent Test**: Unit tests show valid repository harness evidence passes while missing or malformed suite evidence blocks.

- [x] T006 [US1] Implement report data model and static harness source gates in `src/auto_invest/analytics/agent_harness_regression_liveness.py`
- [x] T007 [US1] Implement harness suite summary using existing evaluator functions
- [x] T008 [US1] Implement JSON/Markdown CLI probe in `scripts/agent_harness_regression_liveness_probe.py`

---

## Phase 4: User Story 2 - strict 실행 증거를 WAIT와 FAIL로 분리한다 (Priority: P2)

**Goal**: Supplied strict output and released-work evidence are separated into PASS/WAIT/FAIL gates.

**Independent Test**: Fixture tests cover all-pass, missing strict output wait, degraded strict output fail, malformed released-work fail, and missing released-work wait.

- [x] T009 [US2] Implement strict observation parser and PASS/WAIT/FAIL gate
- [x] T010 [US2] Implement released-work completion gate
- [x] T011 [US2] Add wait/fail fixture assertions in unit tests

---

## Phase 5: User Story 3 - 완료 뒤 다음 운영 보고 후보로 전진한다 (Priority: P3)

**Goal**: Released `candidate-agent-harness-regression-liveness-contract` advances to `candidate-operator-report-liveness-contract`.

**Independent Test**: Focused autonomous-work test changes released-work input and observes selected_work transition.

- [x] T012 [US3] Add next agent-ops frontier template for `candidate-operator-report-liveness-contract`
- [x] T013 [US3] Add completion marker contract for `candidate-agent-harness-regression-liveness-contract`
- [x] T014 [US3] Verify generated next candidate uses risk grade 2 and no safety impact

---

## Phase 6: Validation, PR, and Handoff

- [x] T015 Run focused pytest for agent harness liveness and autonomous-work tests
- [x] T016 Run local quickstart probe and autonomous-work replay
- [x] T017 Run `uv run pytest`
- [x] T018 Run `uv run ruff check src tests`
- [x] T019 Run `git diff --check`
- [x] T020 Run `uv run python scripts/check_handoff_facts.py`
- [x] T021 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T022 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 adds the static harness and suite report.
3. User Story 2 locks strict output and released-work PASS/WAIT/FAIL distinction.
4. User Story 3 closes the autonomous candidate transition.
5. Phase 6 completes verification, merge, deployment observation, and handoff refresh.

## Parallel Opportunities

- T003, T004, and T005 can be drafted independently.
- T006 and T007 are sequential because the report depends on the harness evaluator import.
- T015 and T016 can run after implementation, before the full gate suite.

## Implementation Strategy

Implement MVP first: create the report and probe around harness source and suite evidence, then add strict/released-work gate separation, then mark completion so autonomous-work advances to the operator report liveness candidate.

completed_candidate_id: candidate-agent-harness-regression-liveness-contract
next_candidate_id: candidate-operator-report-liveness-contract
