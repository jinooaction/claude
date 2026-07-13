# Feature Specification: Account Exposure Reservation

**Feature Branch**: `Codex/114-account-exposure-reservation`  
**Created**: 2026-07-13  
**Status**: Draft  
**Input**: Operator asked to continue resolving the remaining execution-safety risks after specs 111-113.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Order bundles cannot exceed account exposure caps (Priority: P1)

As the operator, I need one rebalance run to reserve exposure as it routes orders so that several individually-small BUY orders cannot collectively exceed the account's global or per-symbol cap.

**Why this priority**: This is the precise P0-3 failure mode in `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`.

**Independent Test**: Run a rebalance plan with two BUY orders where each order fits the cap alone but the pair exceeds it; only the safe prefix may route.

**Acceptance Scenarios**:

1. **Given** current exposure is below the global cap, **When** two BUY orders would collectively exceed it, **Then** the second BUY is blocked before broker submission.
2. **Given** a SELL and BUY appear in the same plan, **When** the SELL is still only submitted and not confirmed filled, **Then** the BUY must not spend exposure freed only by the unfilled SELL.

---

### User Story 2 - Open BUY orders count as reserved exposure (Priority: P1)

As the operator, I need already-open BUY orders to count toward account exposure before any new BUY reaches the broker.

**Why this priority**: A broker-accepted but unfilled order is real pending risk. Ignoring it allows another worker or rerun to submit additional BUY exposure against the same stale position snapshot.

**Independent Test**: Seed an open BUY order in the order ledger, then route a new BUY whose notional only violates the cap when the open order is included.

**Acceptance Scenarios**:

1. **Given** an existing `SUBMITTED` BUY order, **When** a new BUY is evaluated, **Then** the global exposure gate includes the open BUY notional.
2. **Given** an existing `SUBMISSION_UNKNOWN` BUY order, **When** a new BUY is evaluated, **Then** it is treated as open until recovery proves otherwise.

---

### User Story 3 - The change stays inside the safety contraction boundary (Priority: P2)

As the operator, I need this work to reduce exposure risk without enabling live trading, changing capital, or weakening existing gates.

**Why this priority**: This is a grade 4 money-path safety change; it must not become an accidental go-live or strategy change.

**Independent Test**: Inspect the diff and validation evidence; no sentinels, whitelist, capital ladder, constitution, or kernel manifest changes are required.

**Acceptance Scenarios**:

1. **Given** the feature branch diff, **When** reviewed, **Then** it only changes reservation calculation, tests, spec artifacts, and handoff records.
2. **Given** the full test suite and lint, **When** run, **Then** existing risk gates and paper/live order-router behavior still pass.

### Edge Cases

- Open SELL orders do not reduce exposure until fills confirm them.
- Open BUY orders in `INTENT`, `SUBMITTED`, `PARTIALLY_FILLED`, or `SUBMISSION_UNKNOWN` are treated as reserved exposure.
- The order currently being evaluated must not count twice after its `INTENT` row is inserted.
- Paper-mode rebalances have no durable `orders` rows, so in-run reservations must still prevent a paper preview from masking the bundle failure.
- Open MARKET BUY orders without a known price are treated conservatively; they cannot reduce the reserved exposure estimate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-114-001**: The system MUST include open BUY order notional when evaluating per-symbol and global exposure caps.
- **FR-114-002**: The system MUST treat `SUBMISSION_UNKNOWN` BUY orders as open exposure until an explicit recovery process resolves them.
- **FR-114-003**: The system MUST exclude the order currently under gate evaluation from open-order reservation to avoid double counting.
- **FR-114-004**: A rebalance run MUST pass cumulative reserved exposure to each routed order instead of reusing one stale snapshot for every BUY.
- **FR-114-005**: Submitted SELL orders MUST NOT reduce reserved exposure until a fill updates positions.
- **FR-114-006**: The feature MUST preserve the existing K1 gate chain and use stricter inputs rather than bypassing or replacing the gates.
- **FR-114-007**: The feature MUST add regression tests for both in-run bundle reservation and pre-existing open BUY reservation.
- **FR-114-008**: The feature MUST NOT change live sentinels, capital allocation, whitelists, configured caps, secrets, constitution, or kernel manifest.

### Key Entities

- **Open Order Reservation**: The notional value of open BUY orders that can still become positions.
- **Reserved Symbol Exposure**: Current symbol exposure plus open BUY notional for that symbol.
- **Reserved Global Exposure**: Current global exposure plus open BUY notional across all symbols.
- **Reservation Scope**: The set of order states that remain unresolved for exposure purposes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-114-001**: A rebalance with multiple BUY orders that collectively exceeds the global cap routes at most the safe prefix and blocks the unsafe remainder.
- **SC-114-002**: A new BUY that is safe without open orders but unsafe with one `SUBMITTED` or `SUBMISSION_UNKNOWN` BUY is rejected before broker submission.
- **SC-114-003**: Existing focused order-router and rebalancer integration tests pass after the change.
- **SC-114-004**: Full `pytest`, `ruff`, PR quality gate, strict agent harness, and handoff fact checks pass before merge.

## Assumptions

- LIMIT orders are the normal money path; if an open BUY lacks a limit price, the system uses available quote context where possible and otherwise stays conservative.
- This spec handles reservation math and account-level serialization within the current process boundary. A dedicated cross-process account lock and central execution authority remain later work.
- `SUBMISSION_UNKNOWN` recovery belongs to spec 112 follow-up work; until then, unknown submissions are reserved exposure.
- Negative-position database constraints and startup ledger/cache verification remain deferred from spec 113.
