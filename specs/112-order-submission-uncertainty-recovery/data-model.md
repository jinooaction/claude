# Data Model: Order Submission Uncertainty Recovery

## RetryPolicy

Application-level request policy.

Fields:

- `retry_transient`: boolean. `True` keeps existing transient retry; `False` sends one attempt only.

Rules:

- Default remains `True` for backward compatibility.
- `place_order` passes `False`.
- Rate limiting and circuit breaker accounting still apply.

## Order State: `SUBMISSION_UNKNOWN`

Persistent order state stored in `orders.state` and `order_state_history.to_state`.

Meaning:

- A broker write was attempted.
- The local process does not have a confirmed KIS order id.
- The system must not assume broker rejection or broker acceptance.
- Automatic replay is forbidden until order/execution history resolves the attempt.

Allowed transition in this feature:

```text
INTENT -> SUBMISSION_UNKNOWN
```

Not an open-order state:

- No `kis_order_id` is available.
- Existing fill-sync open states remain `SUBMITTED` and `PARTIALLY_FILLED`.

## Audit Payload: `ORDER_SUBMISSION_UNKNOWN`

Append-only audit event.

Fields:

- `broker_code`: exception or classifier name.
- `broker_message`: masked human-readable diagnostics summary.
- `diagnostics`: optional masked diagnostics dictionary.
- `next_action`: operator-facing recovery instruction.

Invariants:

- Must not contain raw account number, product code, access token, app key, app secret, or other credential material.
- Must use the same `correlation_id` as the corresponding `ORDER_INTENT`.
- Must not include `kis_order_id` unless a later feature proves one.

## Classification

`SUBMISSION_UNKNOWN`:

- HTTP status 500-599 from order-submit endpoint.
- `httpx.TransportError` from order-submit endpoint.
- Non-JSON response after order-submit write.
- Missing accepted order id with no explicit KIS business rejection.

`REJECTED_BY_BROKER`:

- HTTP 200 response with KIS business rejection fields such as `rt_cd != "0"` or meaningful `msg_cd/msg1`.
- Validation or request shape errors that prove KIS did not accept an order.

`SUBMITTED`:

- KIS response includes accepted order id.
