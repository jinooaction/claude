# Contract: Order Submission Boundary

## Purpose

This contract defines the behavior at the only live broker write boundary used by `OrderRouter.submit_order`.

## Allowed Effects

- Build one KIS overseas order request from a gated `OrderRequest`.
- Send at most one HTTP `POST` to `/uapi/overseas-stock/v1/trading/order` per order correlation id.
- Persist `SUBMITTED`, `REJECTED_BY_BROKER`, or `SUBMISSION_UNKNOWN`.
- Append corresponding audit event.

## Forbidden Effects

- Retrying the same 신규 주문 `POST` automatically after a 5xx or transport failure.
- Treating an ambiguous write failure as confirmed broker rejection.
- Setting `kis_order_id` without a KIS accepted order id.
- Starting a live worker, changing live sentinels, or altering capital.
- Calling KIS in tests.

## State Contract

```text
INTENT -> SUBMITTED
INTENT -> REJECTED_BY_BROKER
INTENT -> SUBMISSION_UNKNOWN
INTENT -> REJECTED_BY_GATE
```

`SUBMISSION_UNKNOWN` requires operator or future recovery lookup before any retry.

## Audit Contract

`ORDER_SUBMISSION_UNKNOWN` must include:

- masked diagnostics
- broker code
- broker message
- next action text

It must not claim the order was rejected or accepted.

## Retry Contract

Read-only requests:

- Transient retry remains enabled by default.

New order submission:

- Transient retry is disabled at the request call site.
- Circuit breaker still observes the transient failure.
