# Tasks: Account Exposure Reservation

**Input**: Design documents from `specs/114-account-exposure-reservation/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required. This is a grade 4 execution-safety change and must use failing regression tests first.

## Phase 1: Setup

- [x] T001 Create SDD artifacts in `specs/114-account-exposure-reservation/`
- [x] T002 Point `.specify/feature.json` at `specs/114-account-exposure-reservation`

---

## Phase 2: Foundational Tests

- [x] T003 [P] Add open-order reservation regression in `tests/integration/test_order_router.py`
- [x] T004 [P] Add in-run rebalance reservation regression in `tests/integration/test_spec_032_live_rebalancer.py`
- [x] T005 Run the focused new tests and confirm they fail for the expected old behavior

---

## Phase 3: User Story 1 - Rebalance Bundle Reservation (Priority: P1)

**Goal**: Later BUY orders in one rebalance see earlier accepted BUY reservations.

**Independent Test**: `test_rebalance_reserves_successful_buys_before_next_buy`

- [x] T006 [US1] Update `src/auto_invest/execution/rebalancer.py` to pass cumulative reserved exposure when durable order rows are unavailable
- [x] T007 [US1] Verify the rebalance regression turns green

---

## Phase 4: User Story 2 - Open BUY Reservation (Priority: P1)

**Goal**: New BUY orders include already-open BUY notional before the K1 gates run.

**Independent Test**: `test_submit_order_counts_open_buy_orders_as_reserved_global_exposure`

- [x] T008 [US2] Add reservation helper in `src/auto_invest/execution/exposure_reservation.py`
- [x] T009 [US2] Wire reservation helper into `src/auto_invest/execution/order_router.py`
- [x] T010 [US2] Verify the order-router regression turns green

---

## Phase 5: Safety Boundary and Validation (Priority: P2)

- [x] T011 [P] Verify no live sentinel, capital, whitelist, constitution, or kernel manifest files changed
- [x] T012 Run focused router and rebalancer suites
- [x] T013 Run `uv run pytest -q`
- [x] T014 Run `uv run ruff check src tests`
- [x] T015 Run `git diff --check`
- [x] T016 Run `uv run python scripts/check_handoff_facts.py`
- [x] T017 Run `uv run python scripts/agent_harness_probe.py --strict`
- [x] T018 Update PR body with risk grade, safety boundary, validation, and handoff evidence
- [x] T019 Merge when tests, lint, PR quality gate, and mergeability are clean
- [x] T020 Refresh `HANDOFF.md` after merge and validate it

## Dependencies & Execution Order

- Phase 1 before all implementation.
- Phase 2 tests must fail before implementation tasks T006-T009.
- US1 and US2 can be implemented in either order after red tests, but both are required before validation.
- Handoff refresh happens only after the feature PR reaches `main`.

## Implementation Strategy

Keep the change narrow:
1. Prove the old failure with focused tests.
2. Add a small reservation helper over existing order rows.
3. Feed stricter exposure inputs into the existing K1 gates.
4. Preserve paper-mode behavior by keeping paper facts out of durable `orders` while tracking in-run reservations.
