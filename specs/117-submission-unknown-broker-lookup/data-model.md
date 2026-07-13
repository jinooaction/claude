# Data Model: Submission Unknown Broker Lookup

## UnknownSubmission

- `correlation_id`: Local order identifier.
- `rule_id`: Rule that created the order.
- `symbol`: Ordered symbol.
- `side`: `BUY` or `SELL`.
- `qty`: Local requested quantity.
- `state`: Must be `SUBMISSION_UNKNOWN`.
- `kis_order_id`: Must be null before recovery.

## BrokerExecution Match

- `kis_order_id`: Broker order id to attach if matched.
- `symbol`: Must equal local symbol.
- `side`: Must equal local side when provided.
- `filled_qty`: Broker cumulative filled quantity.
- `unfilled_qty`: Broker remaining quantity when provided.
- `terminal`: Existing fill planner uses this after recovery.

## Recovery State Transitions

```text
SUBMISSION_UNKNOWN --unique strong broker match--> SUBMITTED
SUBMISSION_UNKNOWN --no match--> SUBMISSION_UNKNOWN
SUBMISSION_UNKNOWN --ambiguous match--> SUBMISSION_UNKNOWN
SUBMISSION_UNKNOWN --lookup failure--> SUBMISSION_UNKNOWN
```

After `SUBMITTED`, the existing fill planner may move the same order to `PARTIALLY_FILLED`, `FILLED`, or `EXPIRED`.

## Audit Events

- `ORDER_SUBMISSION_RECOVERED`: New append-only event containing recovered `kis_order_id`, match reason, broker filled quantity, broker unfilled quantity, and broker terminal flag.
- `ERROR`: Existing event used for lookup failures and ambiguity warnings that should be visible without mutating order state.

