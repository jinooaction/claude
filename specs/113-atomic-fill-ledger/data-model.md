# Data Model: Atomic Fill Ledger

## Fill Application Transaction

Represents one local application of a planned fill sync result.

Fields:

- `started_at`: implicit database transaction start
- `fills`: planned broker fills
- `transitions`: planned order state transitions
- `ts_iso`: deterministic event timestamp passed by worker tick or generated locally

Rules:

- The transaction starts before the first `fills` write.
- The transaction commits only after fill rows, audit rows, position cache updates, and order transitions complete.
- Any exception rolls back all writes in the transaction.

## Inserted Fill

Represents a fill that successfully inserted into `fills`.

Fields:

- `order_correlation_id`
- `kis_fill_id`
- `qty`
- `price_usd`
- `executed_at_utc`
- `commission_usd`

Rules:

- `kis_fill_id` is unique and is the idempotency key.
- Only inserted fills produce a `FILL` audit event.
- Only inserted fills update `current_positions`.

## Skipped Duplicate Fill

Represents a planned fill whose `kis_fill_id` already exists.

Rules:

- Does not append `FILL`.
- Does not update `current_positions`.
- Does not contribute to `fills_applied` or `qty_applied`.
- Does not prevent independent order transitions in the same plan from applying.

## Position Cache Update

Represents the derived `current_positions` update for an inserted fill.

Rules:

- BUY increases quantity and recomputes weighted average cost.
- SELL decreases quantity and keeps average cost unchanged.
- Quantity zero removes the row.
- Full negative-position policy is deferred.
