# Tasks: KIS Order Diagnostics

**Input**: Design documents from `specs/059-kis-order-diagnostics/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because this feature changes a real-money operating path and K4 audit evidence.

## Phase 1: Setup

- [X] T001 Create broker diagnostics contract tests in `tests/integration/test_broker_order_diagnostics.py`.
- [X] T002 Extend micro workflow safety tests in `tests/unit/test_micro_gtaa_canary.py`.

---

## Phase 2: Foundational

- [X] T003 Implement masked broker diagnostics helpers in `src/auto_invest/broker/diagnostics.py`.
- [X] T004 Add optional diagnostics field to `OrderRejectedByBrokerPayload` in `src/auto_invest/persistence/audit.py`.

---

## Phase 3: User Story 1 - Prove Live Order Preconditions Before Submission (Priority: P1)

**Goal**: Armed micro GTAA live runs prove regular-session and cash prerequisites before broker mutation.

**Independent Test**: `uv run pytest tests/unit/test_micro_gtaa_canary.py`

- [X] T005 [US1] Add preflight step and sidecar section to `.github/workflows/rebalance-micro-gtaa-canary.yml`.
- [X] T006 [US1] Gate pre-live breaker and live step on `steps.preflight.outputs.ok == 'true'` in `.github/workflows/rebalance-micro-gtaa-canary.yml`.

---

## Phase 4: User Story 2 - Match KIS Order Request Shape to Current Official Samples (Priority: P2)

**Goal**: KIS normal-order requests match the official required field shape.

**Independent Test**: `uv run pytest tests/integration/test_broker_order_diagnostics.py`

- [X] T007 [US2] Build normal-order payload with KIS sample fields in `src/auto_invest/broker/overseas.py`.
- [X] T008 [US2] Wrap KIS order exceptions with sanitized diagnostics in `src/auto_invest/broker/overseas.py`.

---

## Phase 5: User Story 3 - Preserve Evidence Needed to Confirm Broker Rejections (Priority: P3)

**Goal**: Broker rejection results preserve response evidence without secrets.

**Independent Test**: `uv run pytest tests/integration/test_broker_order_diagnostics.py`

- [X] T009 [US3] Persist diagnostics through `OrderRouter` rejection handling in `src/auto_invest/execution/order_router.py`.
- [X] T010 [US3] Emit diagnostics in `rebalance-once --json` result reasons through existing result serialization in `src/auto_invest/cli.py`.

---

## Phase N: Polish & Validation

- [X] T011 Run `uv run pytest tests/integration/test_broker_order_diagnostics.py tests/unit/test_micro_gtaa_canary.py`.
- [X] T012 Run `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`.
- [X] T013 Run `uv run pytest`.
- [X] T014 Run `uv run ruff check src tests`.
- [ ] T015 Update PR body, merge if eligible, and refresh handoff after merge.

## Dependencies & Execution Order

- T001-T002 define failing tests first.
- T003-T004 are shared diagnostics foundation.
- T005-T006 implement the micro preflight gate and are independent of broker payload changes after T002.
- T007-T009 implement broker request conformance and durable diagnostics after T003-T004.
- T010 uses the existing CLI result path after T009.
- Validation runs after all user stories are complete.

## Parallel Opportunities

- T001 and T002 can be written independently.
- T005-T006 can proceed in parallel with T007-T009 after foundational diagnostics are in place.

## Implementation Strategy

Deliver the preflight block first so no further live order reaches KIS in the known-invalid time/cash states. Then fix request shape and diagnostics. Do not trigger a live retry during implementation.
