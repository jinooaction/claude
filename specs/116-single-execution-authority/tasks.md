# Tasks: Single Execution Authority

**Input**: Design documents from `specs/116-single-execution-authority/`  
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/

**Tests**: Required. This is a grade 4 execution-safety change and must use failing regression tests first.

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/116-single-execution-authority/`
- [x] T002 Point `.specify/feature.json` at `specs/116-single-execution-authority`

## Phase 2: Foundational Tests

- [x] T003 [P] Add authority lock tests in `tests/unit/test_execution_authority.py`
- [x] T004 [P] Tighten broker mutation AST guard in `tests/unit/test_live_order_path.py`
- [x] T005 [P] Add router busy-lock rejection test in `tests/integration/test_order_router.py`
- [x] T006 [P] Add lifecycle cancel busy-lock test in `tests/integration/test_worker_order_lifecycle.py`
- [x] T007 Run focused tests and confirm they fail for the expected old behavior

## Phase 3: User Story 1 - Single broker mutation owner

- [x] T008 Add `src/auto_invest/execution/authority.py`
- [x] T009 Move broker mutation imports/calls behind `ExecutionAuthority`
- [x] T010 Verify AST guard passes

## Phase 4: User Story 2 - Live submission serialized before gates

- [x] T011 Add `execution_authority_locks` migration
- [x] T012 Wire live `OrderRouter.submit_order` to acquire authority before reservations and gates
- [x] T013 Preserve paper-mode behavior without lock acquisition
- [x] T014 Verify router focused tests pass

## Phase 5: User Story 3 - Lifecycle cancel serialized

- [x] T015 Construct one authority per live worker/router
- [x] T016 Wire lifecycle cancel through `ExecutionAuthority`
- [x] T017 Verify lifecycle focused tests pass

## Phase 6: Validation and Handoff

- [x] T018 Run adjacent router, lifecycle, and rebalancer suites
- [x] T019 Run `uv run pytest -q`
- [x] T020 Run `uv run ruff check src tests`
- [x] T021 Run `git diff --check`
- [x] T022 Run `uv run python scripts/check_handoff_facts.py`
- [x] T023 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T024 Create PR with risk grade, safety boundary, validation, and handoff evidence
- [x] T025 Merge when clean
- [x] T026 Refresh `HANDOFF.md` after merge and validate it

## Dependencies

- T003-T006 before implementation.
- T008-T014 before lifecycle cancel wiring.
- T018-T023 before PR merge.
