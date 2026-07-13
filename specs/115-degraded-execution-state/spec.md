# Feature Specification: Degraded Execution State

**Feature Branch**: `codex/115-degraded-execution-state`  
**Created**: 2026-07-13  
**Status**: Draft  
**Input**: Operator asked to continue resolving all remaining execution-safety risks after spec 114.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unknown account state blocks new BUY orders (Priority: P1)

As the operator, I need the system to stop opening new exposure when order, fill, reconciliation, NAV, or loss-state evidence is unclear.

**Why this priority**: This closes the P1-1 failure mode in `HANDOFF-115-EXECUTION-SAFETY-STABILIZATION.md`: the worker can keep buying after critical state reads fail.

**Independent Test**: Seed or inject degraded evidence, submit a BUY, and verify it is rejected before broker submission.

**Acceptance Scenarios**:

1. **Given** a `SUBMISSION_UNKNOWN` BUY remains unresolved, **When** a new BUY is evaluated, **Then** the new BUY is rejected by the degraded execution state gate.
2. **Given** the latest reconciliation result is `INCONCLUSIVE`, **When** a new BUY is evaluated, **Then** the new BUY is rejected until a later `OK` reconciliation exists.
3. **Given** live fill sync fails for open orders, **When** a triggered BUY is evaluated in the same tick, **Then** the BUY is rejected before broker submission.
4. **Given** NAV refresh is enabled and the broker NAV read fails, **When** a triggered BUY is evaluated, **Then** the BUY is rejected before broker submission.
5. **Given** circuit-breaker loss evaluation cannot mark an open position, **When** a triggered BUY is evaluated, **Then** the BUY is rejected until marks are fresh again.

---

### User Story 2 - Degraded mode remains sell-only, not fully frozen (Priority: P1)

As the operator, I need state uncertainty to prevent new exposure while preserving exits and recovery actions.

**Why this priority**: The safety contraction should not trap the account by blocking exposure-reducing orders.

**Independent Test**: Inject a degraded state and submit a SELL; verify the broker submission path is still reachable.

**Acceptance Scenarios**:

1. **Given** execution state is `DEGRADED_SELL_ONLY`, **When** a SELL is routed, **Then** the degraded-state gate allows it to continue through the normal K1 gate chain.
2. **Given** an existing halt flag, **When** any order is routed, **Then** the existing halt gate still blocks it.

---

### User Story 3 - Safety boundary stays narrower than execution authority work (Priority: P2)

As the operator, I need this PR to close degraded-state BUY blocking without mixing in account locks or a full execution authority rewrite.

**Why this priority**: Cross-process locking and single authority are larger follow-up risks; mixing them would make review and rollback harder.

**Independent Test**: Inspect diff and validation evidence; no live sentinels, capital allocations, caps, whitelist, kernel manifest, or constitution files change.

### Edge Cases

- Paper mode does not poll live fills or NAV and must remain byte-compatible unless a test injects a degraded state directly.
- Absence of any reconciliation run is not itself degraded; only the latest explicit `INCONCLUSIVE` result blocks BUY.
- `MISMATCH` reconciliation still relies on the existing halt flag and is not reimplemented here.
- `SUBMISSION_UNKNOWN` SELL does not block BUY by itself; only unresolved BUY submissions can become new exposure.
- A later successful fill sync, NAV refresh, or loss mark evaluation clears the matching runtime blocker.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-115-001**: The system MUST expose an execution state with at least `HEALTHY`, `DEGRADED_SELL_ONLY`, and `HALTED`.
- **FR-115-002**: New BUY orders MUST be rejected before broker submission when execution state is `DEGRADED_SELL_ONLY`.
- **FR-115-003**: SELL orders MUST remain eligible to pass the existing gate chain when execution state is `DEGRADED_SELL_ONLY`.
- **FR-115-004**: An unresolved `SUBMISSION_UNKNOWN` BUY MUST degrade execution state until resolved outside this PR.
- **FR-115-005**: The latest `INCONCLUSIVE` reconciliation run MUST degrade execution state until a later `OK` reconciliation run exists.
- **FR-115-006**: Live fill-sync failure with open orders MUST degrade execution state and a later non-error sync MUST clear that runtime blocker.
- **FR-115-007**: NAV refresh failure when capital tracking is enabled MUST degrade execution state and a later successful NAV refresh MUST clear that runtime blocker.
- **FR-115-008**: Circuit-breaker evaluation with unmarked open positions MUST degrade execution state and a later fully marked evaluation MUST clear that runtime blocker.
- **FR-115-009**: The feature MUST preserve existing halt, K1 exposure, whitelist, and broker submission semantics.
- **FR-115-010**: The feature MUST NOT change live sentinels, capital allocation, whitelists, configured cap values, secrets, constitution, or kernel manifest.

### Key Entities

- **Execution State**: Current account execution mode derived from persisted evidence and worker runtime blockers.
- **Runtime Blocker**: A live worker observation such as fill-sync error, NAV error, or unmarked loss state that is not durable enough to store as a new account state.
- **Persisted Blocker**: A durable database condition such as unresolved `SUBMISSION_UNKNOWN` BUY or latest `INCONCLUSIVE` reconciliation.
- **Sell-Only Mode**: A degraded state that blocks exposure-increasing BUY orders while allowing SELL orders and recovery actions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-115-001**: A BUY routed while execution state is degraded is rejected by `execution_state_gate` and does not call the broker order endpoint.
- **SC-115-002**: A SELL routed while execution state is degraded can still submit when other gates allow it.
- **SC-115-003**: Worker ticks with fill-sync failure or NAV failure produce BUY rejection instead of broker submission.
- **SC-115-004**: Full `pytest`, `ruff`, PR quality gate, strict agent harness, and handoff fact checks pass before merge.

## Assumptions

- `SUBMISSION_UNKNOWN` automated broker lookup recovery remains a later repair; this feature blocks new BUY while the uncertainty remains.
- Cross-process account locks and a single `ExecutionAuthority` are intentionally deferred to spec 116.
- No real broker order, server process inspection, KIS account lookup, or live sentinel update is part of this work.

## Release Ledger

completed_candidate_id: candidate-degraded-execution-state
next_candidate_id: candidate-single-execution-authority
