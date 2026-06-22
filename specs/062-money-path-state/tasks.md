# Tasks: Money Path State Guard

**Input**: Design documents from `/specs/062-money-path-state/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this is an operational-state regression guard for real-money status.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish SDD pointer and existing surface choice.

- [x] T001 Update `.specify/feature.json` to point to `specs/062-money-path-state`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the read-only status contract before changing behavior.

- [x] T002 Add SDD artifacts in `specs/062-money-path-state/`
- [x] T003 [P] Add contract for `live_money_state` in `specs/062-money-path-state/contracts/live-money-state.md`

---

## Phase 3: User Story 1 - Immediate Live Money State (Priority: P1) MVP

**Goal**: The money-path report begins with the current live-money state and cannot hide `micro GTAA armed:true` under older ladder history.

**Independent Test**: Run the money-path unit and integration tests with an armed micro request and confirm JSON/text report `REAL_ORDER_PATH_ARMED`.

### Tests for User Story 1

- [x] T004 [P] [US1] Add `armed:true` live-money state unit tests in `tests/unit/test_money_path.py`
- [x] T005 [P] [US1] Add money-path probe integration test for micro GTAA sidecar consumption in `tests/integration/test_money_path_probe.py`

### Implementation for User Story 1

- [x] T006 [US1] Add `LiveMoneyState` and micro GTAA classification in `src/auto_invest/analytics/money_path.py`
- [x] T007 [US1] Extend `scripts/money_path_probe.py` to parse `automation/rebalance-micro-gtaa.request` and `rebalance-micro-gtaa-last-run`
- [x] T008 [US1] Extend `.github/workflows/money-path.yml` trigger paths if needed for micro state reporting changes

---

## Phase 4: User Story 2 - Evidence Priority Over History (Priority: P2)

**Goal**: The report presents micro live state before first-capital ETA and distinguishes last run evidence from current arming intent.

**Independent Test**: A report with ladder rung 0 and micro `armed:true` shows real-money state first and retains ladder ETA as secondary context.

### Tests for User Story 2

- [x] T009 [P] [US2] Add text ordering and last-run evidence tests in `tests/unit/test_money_path.py`

### Implementation for User Story 2

- [x] T010 [US2] Render `실제 돈 최상위 상태` above ladder stage in `src/auto_invest/analytics/money_path.py`
- [x] T011 [US2] Ensure old sidecar formats without preflight are explicit but non-fatal in `scripts/money_path_probe.py`

---

## Phase 5: User Story 3 - Regression Guard for Agent Reasoning (Priority: P3)

**Goal**: Handoff and tests make the current evidence priority reproducible for later sessions.

**Independent Test**: A new session can identify the live money state by following handoff guidance and running the focused test.

### Tests for User Story 3

- [x] T012 [P] [US3] Add manifest regression test that `rebalance-micro-gtaa-last-run` is consumed in `tests/integration/test_money_path_probe.py`

### Implementation for User Story 3

- [x] T013 [US3] Update `HANDOFF.md` current-state guidance to prioritize money-path live-money state and micro sentinel evidence

---

## Phase 6: Polish & Validation

**Purpose**: Full validation and merge readiness.

- [x] T014 Run focused tests: `uv run pytest tests/unit/test_money_path.py tests/integration/test_money_path_probe.py tests/unit/test_micro_gtaa_canary.py`
- [x] T015 Run governance checks: `uv run python scripts/check_handoff_facts.py` and `uv run python scripts/agent_harness_probe.py --strict`
- [x] T016 Run full validation: `uv run pytest` and `uv run ruff check src tests`
- [x] T017 Update PR body with risk grade, problem definition, evidence, validation, and rollback plan

---

## Dependencies & Execution Order

- Phase 1 and Phase 2 complete before implementation.
- US1 is MVP and must complete before US2.
- US3 depends on US1/US2 behavior being finalized.
- Full validation happens after all story work.

## Parallel Opportunities

- T004 and T005 can run in parallel before implementation.
- T009 and T012 are separate tests but should be finalized after the output contract settles.

## Implementation Strategy

1. Add tests for the current failure mode.
2. Extend the existing money-path report rather than creating a parallel status document.
3. Update handoff only after the report behavior is verified.
