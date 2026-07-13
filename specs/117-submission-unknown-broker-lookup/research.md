# Research: Submission Unknown Broker Lookup

## Decision: Reuse fill sync rather than add a new worker loop

**Rationale**: `sync_fills` already owns read-only KIS order/execution history polling, error isolation, fill planning, and state transitions. Extending it keeps recovery and fill application on one broker evidence snapshot.

**Alternatives considered**:

- Separate recovery worker: rejected because it would duplicate broker polling and create another state transition surface.
- Router-time recovery: rejected because order submission must not immediately retry or poll in the same failure path.

## Decision: Match only on symbol, side, and total quantity

**Rationale**: The local unknown row has no broker order id. Matching must be strong enough to avoid binding the wrong broker order. `filled_qty + unfilled_qty == local qty` proves total accepted quantity for unfilled or partial orders. If `unfilled_qty` is absent, only full-fill equality is safe.

**Alternatives considered**:

- Match on symbol only: rejected as unsafe because repeated same-symbol orders could collide.
- Match on price: rejected as a secondary filter only; KIS execution rows may omit price for unfilled orders.
- Treat no match as rejected: rejected because KIS history gaps are not proof of non-acceptance.

## Decision: Transition recovered orders to `SUBMITTED` first

**Rationale**: Existing fill ingestion already knows how to move `SUBMITTED` to `PARTIALLY_FILLED`, `FILLED`, or `EXPIRED`. Recovery should only restore the missing broker id and let the established planner handle fills.

**Alternatives considered**:

- Directly transition unknown to filled: rejected because it would duplicate fill planner behavior.
- Add a new `RECOVERED` order state: rejected because existing gate and fill logic already understand `SUBMITTED`.

