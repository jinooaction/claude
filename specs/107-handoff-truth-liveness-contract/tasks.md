# Tasks: HANDOFF Truth Liveness Contract

**Input**: Design documents from `specs/107-handoff-truth-liveness-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required because this changes operating-system evidence and autonomous next-work completion behavior.

## Phase 1: Setup

- [x] T001 Update active feature pointers in `.specify/feature.json` and `CLAUDE.md`
- [x] T002 [P] Create SDD artifacts in `specs/107-handoff-truth-liveness-contract/`

---

## Phase 2: Foundational

**Purpose**: Establish contract expectations before implementation.

- [x] T003 [P] Add HANDOFF truth liveness unit tests in `tests/unit/test_handoff_truth_liveness.py`
- [x] T004 [P] Add autonomous-work completion transition coverage in `tests/unit/test_autonomous_work_execution.py`

---

## Phase 3: User Story 1 - HANDOFF 사실성을 계약으로 본다 (Priority: P1)

**Goal**: A deterministic report exposes HANDOFF truth, gates, baselines, completion marker, and next candidate.

**Independent Test**: Unit tests show current and fixture HANDOFF reports produce expected JSON/Markdown fields.

- [x] T005 [US1] Implement report data model and checker wrapper in `src/auto_invest/analytics/handoff_truth_liveness.py`
- [x] T006 [US1] Implement JSON/Markdown CLI probe in `scripts/handoff_truth_liveness_probe.py`

---

## Phase 4: User Story 2 - handoff-only 머지를 stale로 오판하지 않는다 (Priority: P2)

**Goal**: Valid handoff-only first-parent baselines pass, but stale HANDOFF rows block.

**Independent Test**: Fixture tests cover origin-main match, handoff-only first-parent match, stale row block, and expected-row mismatch.

- [x] T007 [US2] Expose allowed baseline classification and HANDOFF fact gates in `src/auto_invest/analytics/handoff_truth_liveness.py`
- [x] T008 [US2] Add stale and handoff-only fixture assertions in `tests/unit/test_handoff_truth_liveness.py`

---

## Phase 5: User Story 3 - 완료 뒤 PR/merge 증거 후보로 전진한다 (Priority: P3)

**Goal**: Released `candidate-handoff-truth-liveness-contract` advances to `candidate-pr-merge-evidence-liveness-contract`.

**Independent Test**: Focused autonomous-work test changes released-work input and observes selected_work transition.

- [x] T009 [US3] Add completion marker contract for `candidate-handoff-truth-liveness-contract`
- [x] T010 [US3] Verify generated next candidate uses risk grade 2 and no safety impact

---

## Phase 6: Validation, PR, and Handoff

- [x] T011 Run focused pytest for HANDOFF truth and autonomous-work tests
- [x] T012 Run local quickstart probe and autonomous-work replay
- [x] T013 Run `uv run pytest`
- [x] T014 Run `uv run ruff check src tests`
- [x] T015 Run `git diff --check`
- [x] T016 Run `uv run python scripts/check_handoff_facts.py`
- [x] T017 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T018 Prepare PR body, PR quality gate evidence, and release replay evidence

## Dependencies & Execution Order

1. Phase 1 and Phase 2 establish traceability and failing expectations.
2. User Story 1 adds the core contract report.
3. User Story 2 locks the stale-vs-handoff-only distinction.
4. User Story 3 closes the autonomous candidate transition.
5. Phase 6 completes verification, merge, deployment observation, and handoff refresh.

## Parallel Opportunities

- T003 and T004 can be drafted independently.
- T005 and T006 are sequential because the probe depends on the report module.
- T011 and T012 can run after implementation, before the full gate suite.

## Implementation Strategy

Implement MVP first: create the report and probe around `check_handoff_facts.py`, then prove handoff-only baselines and stale HANDOFF fixtures behave differently, then mark completion so autonomous-work advances to PR/merge evidence liveness.
