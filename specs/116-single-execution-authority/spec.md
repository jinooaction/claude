# Feature Specification: Single Execution Authority

**Feature Branch**: `codex/116-single-execution-authority`  
**Created**: 2026-07-13  
**Status**: Draft  
**Input**: Execution safety handoff after specs 111-115.

## Goal

All broker write operations must pass through one execution authority that owns an account-scoped lock before any live order gate or broker mutation can run.

## Non-Goals

- Do not place real orders.
- Do not arm live sentinels, change capital, widen whitelists, or alter position caps.
- Do not rewrite broker read paths, reconciliation, fill sync, or strategy logic.
- Do not merge worker and rebalance business logic into one scheduler.

## Risk Grade

Grade 4: money-path shape changes. The change contracts broker writes and adds a lock, but it touches order submission and cancellation routing.

## User Stories

### User Story 1 - Broker writes have one owner (P1)

As the operator, I need `place_order` and `cancel_order` to be callable only from a single authority module so later audits can prove no parallel broker write path exists.

**Acceptance Criteria**

- `place_order` is imported or called only inside `src/auto_invest/execution/authority.py`.
- `cancel_order` is imported or called only inside `src/auto_invest/execution/authority.py`.
- Worker and rebalancer still reach the broker through existing public workflows, but only by asking the authority.

### User Story 2 - Live submissions are serialized before gate evaluation (P1)

As the operator, I need a live order attempt to hold an account lock before it evaluates open-order reservations and broker submission gates.

**Acceptance Criteria**

- A second live submission for the same account is rejected before broker contact when the lock is already held.
- The rejection is auditable through the existing gate-rejection path.
- The lock is released after success, broker rejection, ambiguous submission, or unexpected exception.

### User Story 3 - Cancels are serialized by the same authority (P1)

As the operator, I need TTL cancel and requote cancel operations to use the same account lock as new order submissions.

**Acceptance Criteria**

- A lifecycle cancel does not contact the broker while another authority holder owns the account lock.
- The local order state remains unchanged when cancel cannot acquire the lock.
- Requote still re-routes the replacement order through the router and authority gate chain.

### User Story 4 - Paper and dry-run stay broker-write-free (P2)

As the operator, I need simulation paths to avoid acquiring live authority or contacting broker write endpoints.

**Acceptance Criteria**

- Paper router behavior remains simulated.
- `rebalance-once --dry-run` still routes no orders and requires no KIS write authority.

## Requirements

- **FR-116-01**: Add an `ExecutionAuthority` module as the only code path that imports and calls broker mutation helpers.
- **FR-116-02**: Add a SQLite-backed account lock with owner, context, acquired time, and expiry.
- **FR-116-03**: Acquire the account lock before live order reservations, gate evaluation, and broker submission.
- **FR-116-04**: Reject live order attempts with `REJECTED_BY_GATE` and gate `execution_authority_lock` when the lock cannot be acquired.
- **FR-116-05**: Use the same authority for lifecycle cancel operations.
- **FR-116-06**: Release locks in `finally` even when broker calls fail.
- **FR-116-07**: Reclaim expired locks so a dead process does not permanently block the account.
- **FR-116-08**: Preserve existing `SUBMISSION_UNKNOWN`, broker rejection, K1 cap, halt, and degraded-state behavior.

## Release Ledger

completed_candidate_id: candidate-single-execution-authority  
next_candidate_id: candidate-operator-report-liveness-contract

## Out of Scope Remaining After This Spec

- Operator-side real server verification of running processes and KIS account state.
- A long-lived authority daemon. This spec implements an in-process authority with a cross-process SQLite lock.
- Automatic `SUBMISSION_UNKNOWN` broker lookup recovery beyond existing degraded buy blocking.
