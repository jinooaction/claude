# Contract: Submission Unknown Broker Lookup

## Allowed Effects

- Read KIS order/execution history through the existing `inquire-ccnl` read-only endpoint.
- Update `orders.kis_order_id`, `orders.submitted_at_utc`, and latest state cache only when a unique strong match exists.
- Append `order_state_history` transition rows.
- Append audit rows.
- Apply normal fill rows and position cache updates through existing fill-sync logic after recovery.

## Forbidden Effects

- No `place_order` call.
- No `cancel_order` call.
- No `order-rvsecncl` call.
- No `AUTO_INVEST_MODE=live` change.
- No live sentinel, capital, whitelist, caps, loss budget, constitution, kernel manifest, secret, or paid-service setting change.
- No assumption that a missing broker match means the order was rejected.

## Strong Match Contract

A broker row can recover a local unknown submission only if all are true:

1. Broker symbol equals local symbol.
2. Broker side equals local side when broker side is present.
3. Quantity is proven:
   - `filled_qty == local qty`, or
   - `unfilled_qty` is present and `filled_qty + unfilled_qty == local qty`.
4. Exactly one broker order id satisfies the match for that local order.

If more than one broker order id satisfies the contract, the local order remains `SUBMISSION_UNKNOWN`.

