# Feature Specification: Submission Unknown Broker Lookup

**Feature Branch**: `codex/117-submission-unknown-broker-lookup`  
**Created**: 2026-07-13  
**Status**: Draft  
**Input**: Remaining execution-safety risk after specs 111-116.

## Goal

When an order is left in `SUBMISSION_UNKNOWN`, the system must use read-only broker order/execution lookup to prove whether KIS accepted the order before new BUY exposure can resume. Proven matches attach the broker order id and re-enter the normal fill-sync path. Unproven or ambiguous matches stay unresolved and continue to block new BUY orders.

## Non-Goals

- Do not place, cancel, modify, or retry any order.
- Do not arm live sentinels, change capital, widen whitelists, or alter position caps.
- Do not query the real KIS account from this development session.
- Do not rewrite the broker execution parser or fill ledger beyond the recovery handoff needed here.
- Do not clear `SUBMISSION_UNKNOWN` merely because no broker match is visible.

## Risk Grade

Grade 4: money-path safety recovery. This change touches live order state recovery and fill synchronization, but it only adds read-only broker lookup and stricter ambiguity handling. It must not add any broker write path.

## User Stories

### User Story 1 - Proven broker acceptance resolves unknown submission (P1)

As the operator, I need an unresolved `SUBMISSION_UNKNOWN` order to recover when broker order/execution history contains one strong match for the same symbol, side, and quantity.

**Acceptance Criteria**

- `sync_fills` polls broker history when unresolved `SUBMISSION_UNKNOWN` orders exist, even if no `SUBMITTED` orders exist.
- A single strong match writes the recovered `kis_order_id`, stores order routing, records an audit event, and transitions `SUBMISSION_UNKNOWN` to `SUBMITTED`.
- Existing fill ingestion then applies fills and terminal transitions from the same broker evidence.

### User Story 2 - Ambiguity stays fail-closed (P1)

As the operator, I need ambiguous or missing broker history to leave the local order unresolved so duplicate exposure remains blocked.

**Acceptance Criteria**

- No match leaves the order in `SUBMISSION_UNKNOWN`.
- More than one possible match leaves the order in `SUBMISSION_UNKNOWN`.
- Read-only lookup failure records an error and does not mutate the order.

### User Story 3 - Recovery is auditable and non-mutating outside state cache (P2)

As the next session, I need to see exactly why a submission unknown was or was not recovered without guessing from state alone.

**Acceptance Criteria**

- Successful recovery appends `ORDER_SUBMISSION_RECOVERED` with the recovered broker id and match summary.
- Recovery does not change append-only audit or fill rows in place.
- Recovery does not introduce any new direct broker write caller outside `ExecutionAuthority`.

## Requirements

- **FR-117-01**: Load unresolved orders where `orders.state = 'SUBMISSION_UNKNOWN'` and `kis_order_id IS NULL`.
- **FR-117-02**: `sync_fills` MUST call read-only `inquire-ccnl` when either open submitted orders or unresolved unknown submissions exist.
- **FR-117-03**: A broker execution is a strong match only when symbol and side match, and the broker-reported total quantity equals the local order quantity.
- **FR-117-04**: Full fills may match by `filled_qty == qty` when `unfilled_qty` is absent.
- **FR-117-05**: Partial or unfilled orders require `filled_qty + unfilled_qty == qty`; otherwise they are not strong enough to recover.
- **FR-117-06**: Exactly one strong match MUST transition the order from `SUBMISSION_UNKNOWN` to `SUBMITTED`, set `kis_order_id`, set `submitted_at_utc`, and store `order_routing`.
- **FR-117-07**: Zero or multiple strong matches MUST leave the order unchanged.
- **FR-117-08**: Recovery MUST append an `ORDER_SUBMISSION_RECOVERED` audit event for successful matches.
- **FR-117-09**: Broker lookup failures MUST append an `ERROR` event and return a result with `error`, without mutating unknown orders.
- **FR-117-10**: Recovered orders MUST be included in the same fill-ingestion planning pass so fills and terminal states are applied without waiting for a later tick.
- **FR-117-11**: `SUBMISSION_UNKNOWN` BUY orders that remain unresolved MUST continue to degrade execution state and block new BUY orders.
- **FR-117-12**: This feature MUST NOT call `place_order`, `cancel_order`, `order-rvsecncl`, or any broker mutation endpoint.
- **FR-117-13**: This feature MUST NOT modify live sentinels, capital, whitelist, caps, loss budget, constitution, kernel manifest, secrets, or external paid-service settings.

## Key Entities

- **UnknownSubmission**: Local order that may have been accepted by KIS but lacks a broker order id.
- **BrokerExecution Match**: Read-only broker order/execution row that can prove acceptance for one unknown submission.
- **Recovery Result**: Count and warning summary returned by fill synchronization after attempting lookup recovery.
- **Recovery Audit Event**: Append-only evidence that a local uncertain order was tied to a specific broker order id.

## Success Criteria

- **SC-117-01**: Focused regression shows `sync_fills` polls `inquire-ccnl` for a lone `SUBMISSION_UNKNOWN` order.
- **SC-117-02**: A unique full-fill match recovers `kis_order_id`, appends `ORDER_SUBMISSION_RECOVERED`, then applies the `FILL` and `FILLED` transition.
- **SC-117-03**: A unique unfilled match recovers to `SUBMITTED` and does not fabricate fills.
- **SC-117-04**: Ambiguous matches leave the order `SUBMISSION_UNKNOWN` with no recovered id.
- **SC-117-05**: Lookup failure leaves the order unchanged and records an `ERROR`.
- **SC-117-06**: Existing submitted-order fill sync behavior remains unchanged.
- **SC-117-07**: `uv run pytest -q`, `uv run ruff check src tests`, `git diff --check`, `uv run python scripts/check_handoff_facts.py`, `uv run python scripts/agent_harness_probe.py --strict`, and the PR quality gate pass before merge.

## Assumptions

- KIS order/execution history contains enough fields to identify symbol, side, filled quantity, and unfilled quantity for accepted but not-yet-filled orders.
- If KIS omits `unfilled_qty`, only full-fill matches are safe to recover.
- A missing match is not proof of rejection; it remains unresolved to prevent duplicate orders.
- The system already blocks new BUY orders while unresolved `SUBMISSION_UNKNOWN` BUY rows exist.

## Release Ledger

completed_candidate_id: candidate-submission-unknown-broker-lookup  
next_candidate_id: candidate-operator-report-liveness-contract

## Out of Scope Remaining After This Spec

- Operator-side real server verification of running processes, KIS open orders, holdings, and GitHub Environment protection.
- Manual remediation playbook for old historical unknown rows if KIS history no longer covers their order date.
