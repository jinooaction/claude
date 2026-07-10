# Tasks: PR/Merge Evidence Liveness Contract

**Input**: Design documents from `specs/108-pr-merge-evidence-liveness-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required because this changes operating-system evidence and autonomous next-work completion behavior.

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/108-pr-merge-evidence-liveness-contract/`

---

## Phase 2: Foundational

**Purpose**: Establish contract expectations before implementation.

- [x] T003 [P] Add PR/merge evidence liveness unit tests in `tests/unit/test_pr_merge_evidence_liveness.py`
- [x] T004 [P] Add probe integration coverage in `tests/integration/test_pr_merge_evidence_liveness_probe.py`
- [x] T005 [P] Add autonomous-work completion transition coverage in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - PR 완료 증거를 계약으로 본다 (Priority: P1)

**Goal**: A deterministic report exposes PR body quality, completion marker, next candidate, and safety boundary.

**Independent Test**: Unit tests show valid PR body evidence passes while missing evidence waits.

- [x] T006 [US1] Implement report data model and PR body quality gate in `src/auto_invest/analytics/pr_merge_evidence_liveness.py`
- [x] T007 [US1] Implement JSON/Markdown CLI probe in `scripts/pr_merge_evidence_liveness_probe.py`

---

## Phase 4: User Story 2 - 머지 뒤 증거 연결을 구분한다 (Priority: P2)

**Goal**: main merge, released-work, and deploy-status evidence are separated into PASS/WAIT/FAIL gates.

**Independent Test**: Fixture tests cover all-pass, missing deploy wait, malformed released-work fail, and failed deploy block.

- [x] T008 [US2] Implement merge, released-work, and deploy observation gates in `src/auto_invest/analytics/pr_merge_evidence_liveness.py`
- [x] T009 [US2] Add wait/fail fixture assertions in `tests/unit/test_pr_merge_evidence_liveness.py`

---

## Phase 5: User Story 3 - 완료 뒤 worktree 동시 작업 후보로 전진한다 (Priority: P3)

**Goal**: Released `candidate-pr-merge-evidence-liveness-contract` advances to `candidate-worktree-concurrency-liveness-contract`.

**Independent Test**: Focused autonomous-work test changes released-work input and observes selected_work transition.

- [x] T010 [US3] Add completion marker contract for `candidate-pr-merge-evidence-liveness-contract`
- [x] T011 [US3] Verify generated next candidate uses risk grade 2 and no safety impact

---

## Phase 6: Validation, PR, and Handoff

- [x] T012 Run focused pytest for PR/merge evidence and autonomous-work tests
- [x] T013 Run local quickstart probe and autonomous-work replay
- [x] T014 Run `uv run pytest`
- [x] T015 Run `uv run ruff check src tests`
- [x] T016 Run `git diff --check`
- [x] T017 Run `uv run python scripts/check_handoff_facts.py`
- [x] T018 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T019 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 adds the core contract report.
3. User Story 2 locks the evidence PASS/WAIT/FAIL distinction.
4. User Story 3 closes the autonomous candidate transition.
5. Phase 6 completes verification, merge, deployment observation, and handoff refresh.

## Parallel Opportunities

- T003, T004, and T005 can be drafted independently.
- T006 and T007 are sequential because the probe depends on the report module.
- T012 and T013 can run after implementation, before the full gate suite.

## Implementation Strategy

Implement MVP first: create the report and probe around PR body quality evidence, then add merge/released/deploy gate separation, then mark completion so autonomous-work advances to worktree concurrency liveness.
