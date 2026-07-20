# Data Model: Security Trust Boundary Hardening

## CanaryPassedPayload

- `candidate_rev`: commit or candidate code hash that passed canary.
- `ruleset_sha256`: SHA-256 of the exact ruleset that passed canary. Optional for legacy parsing, required for new approval.

## ExecutionStateDecision

- `ok`: whether new exposure may proceed.
- `degraded`: whether order execution is ambiguous.
- `reason`: includes stale `INTENT`, stale `SUBMITTING`, `SUBMISSION_UNKNOWN`, reconciliation timeout, or missing mark reason.

## Exposure Effect

- `INCREASE_EXPOSURE`: BUY or unsupported sell state that increases or might increase risk.
- `REDUCE_ONLY`: SELL whose requested quantity is greater than zero and no more than current broker position.
- `OVERSOLD`: SELL quantity exceeds known current position.
- `UNKNOWN_REDUCTION`: SELL quantity cannot be proven against a current position.

## Public Sidecar Redaction

- Account numbers, token-like values, order identifiers, server addresses, NAV, capital, and raw order/result keys are replaced with stable redaction markers before commit to public evidence branches.
