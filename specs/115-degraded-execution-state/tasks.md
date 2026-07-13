# Tasks: Degraded Execution State

**Input**: Design documents from `specs/115-degraded-execution-state/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required. This is a grade 4 execution-safety change and must use failing regression tests first.

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/115-degraded-execution-state/`
- [x] T002 Point `.specify/feature.json` at `specs/115-degraded-execution-state`

---

## Phase 2: Foundational Tests

- [x] T003 [P] Add persisted execution-state tests in `tests/unit/test_execution_state.py`
- [x] T004 [P] Add router BUY block and SELL allow tests in `tests/integration/test_order_router.py`
- [x] T005 [P] Add worker fill-sync failure BUY block test in `tests/integration/test_worker_fill_sync.py`
- [x] T006 [P] Add worker NAV failure BUY block test in `tests/integration/test_worker_capital_tracking.py`
- [x] T006A [P] Add missing loss-mark BUY block test in `tests/integration/test_circuit_breaker_worker.py`
- [x] T007 Run focused new tests and confirm they fail for the expected old behavior

---

## Phase 3: User Story 1 - New BUY blocked under uncertainty (Priority: P1)

**Goal**: Critical uncertain state prevents new exposure before broker submission.

**Independent Test**: New focused tests turn green after implementation.

- [x] T008 [US1] Add execution-state evaluator in `src/auto_invest/execution/execution_state.py`
- [x] T009 [US1] Wire `execution_state_gate` into `src/auto_invest/execution/order_router.py`
- [x] T010 [US1] Wire worker runtime blockers from fill sync, NAV refresh, and missing loss marks
- [x] T011 [US1] Verify focused BUY-blocking tests pass

---

## Phase 4: User Story 2 - Degraded mode remains sell-only (Priority: P1)

**Goal**: SELL orders and recovery routes remain available while BUY is blocked.

- [x] T012 [US2] Ensure `execution_state_gate` permits SELL in `DEGRADED_SELL_ONLY`
- [x] T013 [US2] Verify the SELL focused test passes

---

## Phase 5: Safety Boundary and Validation (Priority: P2)

- [x] T014 [P] Verify no live sentinel, capital, whitelist, constitution, or kernel manifest files changed
- [x] T015 Run focused router, worker fill-sync, worker capital, worker circuit-breaker, and execution-state tests
- [x] T016 Run `uv run pytest -q`
- [x] T017 Run `uv run ruff check src tests`
- [x] T018 Run `git diff --check`
- [x] T019 Run `uv run python scripts/check_handoff_facts.py`
- [x] T020 Run `uv run python scripts/agent_harness_probe.py --strict`
- [ ] T021 Update PR body with risk grade, safety boundary, validation, and handoff evidence
- [ ] T022 Merge when tests, lint, PR quality gate, and mergeability are clean
- [ ] T023 Refresh `HANDOFF.md` after merge and validate it

## Dependencies & Execution Order

- Phase 1 before all implementation.
- Phase 2 tests must fail before implementation tasks T008-T010.
- US1 and US2 share the gate implementation and must both pass before validation.
- Handoff refresh happens only after the feature PR reaches `main`.

## Implementation Strategy

Keep the change narrow:
1. Prove the old failure with focused tests.
2. Add a small execution-state evaluator over existing DB state.
3. Feed worker-local runtime blockers into the same evaluator.
4. Reject BUY through the existing gate-audit path.
5. Preserve SELL, halt, K1, and broker semantics.
