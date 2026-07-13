# Contract: Fill Application Transaction

## Scope

This contract applies to `apply_fill_plan(conn, plan, ts_iso=...)`.

## Inputs

- `conn`: migrated SQLite connection
- `plan.fills`: zero or more planned fills
- `plan.transitions`: zero or more order state transitions
- `ts_iso`: optional deterministic timestamp

## Guarantees

1. New fill application is atomic across:
   - `fills`
   - `audit_log` `FILL`
   - `current_positions`
   - `orders`
   - `order_state_history`
2. Duplicate `kis_fill_id` does not append `FILL` audit and does not update positions.
3. Returned `fills_applied` and `qty_applied` count only inserted fills.
4. Any exception inside the transaction rolls back the transaction.
5. The function performs no broker, SSH, Telegram, Anthropic, or paid external call.

## Forbidden Effects

- Real order submission
- Real order cancellation
- Live sentinel modification
- Capital, whitelist, caps, loss-budget modification
- Constitution or kernel manifest modification

## Regression Evidence

The contract is verified by:

- duplicate planned fill test
- injected failure rollback test
- existing live fill sync integration tests
- full repository gates
