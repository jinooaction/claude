# Research: Order Submission Uncertainty Recovery

## Decision 1: Use a per-request retry switch, not a new client class

**Decision**: Add a request-scoped no-retry option to `ResilientClient.request`.

**Rationale**: The existing client already owns rate limiting, transient classification, and circuit breaker accounting. A per-request option lets read-only calls keep the existing behavior while broker writes opt out at the call site. A new client class would duplicate resilience logic and risk drift.

**Rejected Alternatives**:

- Disable retries globally: would degrade quote, balance, and execution reads.
- Infer by HTTP method only: some `POST` endpoints can be safe read-style APIs and some writes need custom policy. The order adapter should state the policy explicitly.

## Decision 2: Classify transport/5xx order-submit failures as `SUBMISSION_UNKNOWN`

**Decision**: If a write request left the client and failed with `httpx.TransportError`, HTTP 5xx, non-JSON body, or missing accepted order id without an explicit business rejection, the router records `SUBMISSION_UNKNOWN`.

**Rationale**: The local process cannot prove whether KIS accepted the request. Retrying automatically can duplicate orders; treating it as rejected can hide the risk. A distinct state preserves uncertainty and forces lookup before retry.

**Rejected Alternatives**:

- Keep `REJECTED_BY_BROKER`: semantically wrong for ambiguous transport/server failures.
- Mark `SUBMITTED`: unsafe because there is no broker order id and no normal fill-sync handle.

## Decision 3: Keep explicit KIS business rejections as `REJECTED_BY_BROKER`

**Decision**: HTTP 200 responses with `rt_cd != 0` or structured KIS rejection diagnostics stay `REJECTED_BY_BROKER`.

**Rationale**: KIS has explicitly answered that the order was not accepted. These observations should continue feeding existing broker rejection taxonomy and opportunity analysis.

**Rejected Alternatives**:

- Treat all order errors as unknown: loses information and pollutes recovery queues with clear rejections.

## Decision 4: Do not add a database migration

**Decision**: Add the new state and event at application level only.

**Rationale**: `orders.state` and `audit_log.event_type` are text columns without enum check constraints. Historical rows remain valid, and the audit model already evolves by additive `EventType` literals.

**Rejected Alternatives**:

- Add a migration to create enum side tables: unnecessary blast radius for this safety fix.

## Decision 5: Keep full recovery workflow out of scope

**Decision**: The feature records the need for recovery but does not perform broker order lookup and reconciliation automatically.

**Rationale**: Correct recovery requires account/order-history semantics, time windows, id matching, and operator policy. Blindly adding lookup here could create a second unsafe path.

**Rejected Alternatives**:

- Immediately retry after a short delay: reintroduces duplicate risk.
- Guess by symbol/qty/price from recent executions: too much ambiguity for money-path automation.
