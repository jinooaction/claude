# Tasks: Worktree Concurrency Liveness Contract

**Input**: Design documents from `specs/109-worktree-concurrency-liveness-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required because this changes operating-system evidence and autonomous next-work completion behavior.

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/109-worktree-concurrency-liveness-contract/`

---

## Phase 2: Foundational

**Purpose**: Establish contract expectations before implementation.

- [x] T003 [P] Add worktree concurrency liveness unit tests in `tests/unit/test_worktree_concurrency_liveness.py`
- [x] T004 [P] Add probe integration coverage in `tests/integration/test_worktree_concurrency_liveness_probe.py`
- [x] T005 [P] Add autonomous-work completion transition coverage in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - 동시 작업 방어가 살아 있는지 한 번에 본다 (Priority: P1)

**Goal**: A deterministic report exposes session-start, pre-commit, pre-push hook wiring, completion marker, next candidate, and safety boundary.

**Independent Test**: Unit tests show valid repository hook evidence passes while missing hook evidence blocks.

- [x] T006 [US1] Implement report data model and static hook gates in `src/auto_invest/analytics/worktree_concurrency_liveness.py`
- [x] T007 [US1] Implement JSON/Markdown CLI probe in `scripts/worktree_concurrency_liveness_probe.py`

---

## Phase 4: User Story 2 - WARN/BLOCK/isolate/복구 스냅샷 계약을 분리한다 (Priority: P2)

**Goal**: Synthetic guard behavior, recovery snapshot surface, and optional runtime output are separated into PASS/WAIT/FAIL gates.

**Independent Test**: Fixture tests cover all-pass, missing runtime wait, malformed released-work fail, and broken hook block.

- [x] T008 [US2] Implement synthetic guard behavior and recovery snapshot gates in `src/auto_invest/analytics/worktree_concurrency_liveness.py`
- [x] T009 [US2] Add wait/fail fixture assertions in `tests/unit/test_worktree_concurrency_liveness.py`

---

## Phase 5: User Story 3 - 완료 뒤 다음 agent-ops 후보로 전진한다 (Priority: P3)

**Goal**: Released `candidate-worktree-concurrency-liveness-contract` advances to `candidate-agent-harness-regression-liveness-contract`.

**Independent Test**: Focused autonomous-work test changes released-work input and observes selected_work transition.

- [x] T010 [US3] Add next agent-ops frontier template for `candidate-agent-harness-regression-liveness-contract`
- [x] T011 [US3] Add completion marker contract for `candidate-worktree-concurrency-liveness-contract`
- [x] T012 [US3] Verify generated next candidate uses risk grade 2 and no safety impact

---

## Phase 6: Validation, PR, and Handoff

- [x] T013 Run focused pytest for worktree concurrency liveness and autonomous-work tests
- [x] T014 Run local quickstart probe and autonomous-work replay
- [x] T015 Run `uv run pytest`
- [x] T016 Run `uv run ruff check src tests`
- [x] T017 Run `git diff --check`
- [x] T018 Run `uv run python scripts/check_handoff_facts.py`
- [x] T019 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T020 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 adds the static hook report.
3. User Story 2 locks the guard PASS/WAIT/FAIL distinction.
4. User Story 3 closes the autonomous candidate transition.
5. Phase 6 completes verification, merge, deployment observation, and handoff refresh.

## Parallel Opportunities

- T003, T004, and T005 can be drafted independently.
- T006 and T007 are sequential because the probe depends on the report module.
- T013 and T014 can run after implementation, before the full gate suite.

## Implementation Strategy

Implement MVP first: create the report and probe around hook wiring evidence, then add synthetic guard/recovery snapshot gate separation, then mark completion so autonomous-work advances to the agent harness regression liveness candidate.

completed_candidate_id: candidate-worktree-concurrency-liveness-contract
next_candidate_id: candidate-agent-harness-regression-liveness-contract
