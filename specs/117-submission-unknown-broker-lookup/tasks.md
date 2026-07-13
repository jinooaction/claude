# Tasks: Submission Unknown Broker Lookup

**Input**: Design documents from `specs/117-submission-unknown-broker-lookup/`  
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/

**Tests**: Required. This is a grade 4 execution-safety recovery change and must use failing regression tests first.

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/117-submission-unknown-broker-lookup/`
- [x] T002 Point `.specify/feature.json` at `specs/117-submission-unknown-broker-lookup`

## Phase 2: Foundational Tests

- [x] T003 [P] Add unique full-fill recovery test in `tests/integration/test_fill_sync.py`
- [x] T004 [P] Add unique unfilled recovery test in `tests/integration/test_fill_sync.py`
- [x] T005 [P] Add ambiguous match fail-closed test in `tests/integration/test_fill_sync.py`
- [x] T006 [P] Add lookup failure no-mutation test in `tests/integration/test_fill_sync.py`
- [x] T007 Run focused new tests and confirm they fail for the expected old behavior

## Phase 3: User Story 1 - Proven broker acceptance resolves unknown submission

- [x] T008 Add `ORDER_SUBMISSION_RECOVERED` audit payload in `src/auto_invest/persistence/audit.py`
- [x] T009 Add unknown-submission loading and matching helpers in `src/auto_invest/execution/fill_sync.py`
- [x] T010 Apply unique recovery before fill planning in `src/auto_invest/execution/fill_sync.py`
- [x] T011 Verify focused recovery tests pass

## Phase 4: User Story 2 - Ambiguity stays fail-closed

- [x] T012 Preserve unresolved state for zero or multiple matches in `src/auto_invest/execution/fill_sync.py`
- [x] T013 Preserve unresolved state and record error on lookup failure in `src/auto_invest/execution/fill_sync.py`
- [x] T014 Verify ambiguity and failure tests pass

## Phase 5: Safety Boundary and Validation

- [x] T015 [P] Verify no new broker mutation caller in `tests/unit/test_live_order_path.py`
- [x] T016 [P] Verify unresolved `SUBMISSION_UNKNOWN` still degrades execution state in `tests/unit/test_execution_state.py`
- [x] T017 Run adjacent fill-sync, execution-state, and live-order-path tests
- [x] T018 Run `uv run pytest -q`
- [x] T019 Run `uv run ruff check src tests`
- [x] T020 Run `git diff --check`
- [x] T021 Run `uv run python scripts/check_handoff_facts.py`
- [x] T022 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T023 Create PR with risk grade, safety boundary, validation, and handoff evidence
- [x] T024 Merge when tests, lint, PR quality gate, and mergeability are clean
- [x] T025 Refresh `HANDOFF.md` after merge and validate it

## Dependencies

- T001-T002 before all implementation.
- T003-T007 before implementation tasks T008-T014.
- T008-T010 before fill application validation.
- T017-T022 before PR merge.

## Implementation Strategy

1. Prove the old failure with focused tests.
2. Add the smallest recovery planner inside fill sync.
3. Recover only unique strong matches.
4. Let existing fill planner apply fills after recovery.
5. Preserve unresolved uncertainty as a BUY blocker.
