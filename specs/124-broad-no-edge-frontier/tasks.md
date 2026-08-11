# Tasks: Broad NO_EDGE Frontier

**Input**: Design documents from `specs/124-broad-no-edge-frontier/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/broad-no-edge-frontier.md`

## Phase 1: Setup

- [x] T001 Create SDD artifacts for `specs/124-broad-no-edge-frontier/`.
- [x] T002 Point `.specify/feature.json` at the active feature directory.

## Phase 2: Parent Suppression (P1)

- [x] T003 [US1] Add regression coverage in `tests/unit/test_autonomous_work_execution.py` proving a released parent broad no-edge candidate does not reappear with a new fingerprint.
- [x] T004 [US1] Update `src/auto_invest/analytics/autonomous_work_execution.py` so parent broad no-edge fingerprinting ignores broad no-edge parent/follow-up releases.

## Phase 3: Follow-Up Map (P2)

- [x] T005 [US2] Add deterministic map and selection tests in `tests/unit/test_autonomous_work_execution.py`.
- [x] T006 [US2] Add broad no-edge map templates, map entries, report serialization, markdown rendering, and follow-up packet selection in `src/auto_invest/analytics/autonomous_work_execution.py`.

## Phase 4: Safety and Verification (P3)

- [x] T007 [US3] Verify focused autonomous-work tests pass.
- [x] T008 [US3] Run full pytest and ruff.
- [x] T009 [US3] Run handoff fact and agent harness probes.
- [ ] T010 [US3] Create PR with quality gate evidence, merge when eligible, and refresh HANDOFF if needed.

## Dependencies & Execution Order

- T001 and T002 must precede implementation.
- T003 must precede T004.
- T005 must precede T006.
- T007 through T010 are sequential closeout gates.
