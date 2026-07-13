# Research: Account Exposure Reservation

## Decision: Count open BUY orders as reserved exposure

**Rationale**: A submitted or unknown BUY can still become a position. Ignoring it lets a later BUY reuse the same exposure headroom.

**Alternatives considered**:
- Count only filled positions: rejected because this is the current bug.
- Count SELL orders as negative exposure: rejected because an unfilled SELL has not reduced the position.

## Decision: Preserve the existing K1 gates

**Rationale**: The gates already enforce per-trade, per-symbol, and global caps. Feeding them reserved exposure numbers gives the same audit semantics while tightening the safety input.

**Alternatives considered**:
- Add a parallel reservation gate: rejected because it would duplicate K1 logic and split audit semantics.

## Decision: Exclude the current order's correlation id

**Rationale**: The router inserts the `INTENT` row before gate evaluation. Counting that row as an open order and then adding the request delta inside the gate would double count the current order.

**Alternatives considered**:
- Move intent insertion after gates: rejected because existing audit/order lifecycle assumes intent exists before gate rejection transitions.

## Decision: Rebalancer tracks in-run reservations when the router cannot

**Rationale**: Paper mode and test routers do not write durable order rows, so in-run BUY reservations must still be visible to later orders in the same plan.

**Alternatives considered**:
- Require paper mode to write `orders` rows: rejected because existing paper-mode contract deliberately keeps paper facts in `audit_log` only.

## Decision: Cross-process account lock remains follow-up

**Rationale**: This spec can close stale snapshot and open-order undercounting without adding a new lock service. A true cross-process execution authority is still planned for the later single-authority milestone.

**Alternatives considered**:
- Add SQLite account locks now: rejected to keep this PR focused and avoid inventing a partial authority layer before spec 116.
