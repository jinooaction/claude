# Data Model: Degraded Execution State

## ExecutionState

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `status` | `ExecutionStatus` | yes | `HEALTHY`, `DEGRADED_SELL_ONLY`, or `HALTED` |
| `reasons` | `tuple[ExecutionStateReason, ...]` | yes | Empty when healthy |

## ExecutionStateReason

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `code` | `str` | yes | Stable machine-readable reason |
| `detail` | `str` | yes | Operator-readable explanation |

## Persisted Blockers

| Blocker | Source | Degraded When | Clear Condition |
|---------|--------|---------------|-----------------|
| `submission_unknown_buy` | `orders` | At least one BUY is `SUBMISSION_UNKNOWN` | Recovery changes the order out of `SUBMISSION_UNKNOWN` |
| `reconciliation_inconclusive` | `reconciliation_runs` | Latest run result is `INCONCLUSIVE` | Later run result is `OK` |

## Runtime Blockers

| Blocker | Source | Degraded When | Clear Condition |
|---------|--------|---------------|-----------------|
| `fill_sync_error` | Worker tick | Live fill sync for open orders returns an error or raises | Later fill sync returns no error |
| `nav_refresh_error` | Worker tick | Capital tracking NAV refresh fails | Later NAV refresh succeeds |
| `loss_marks_missing` | Worker tick | Circuit-breaker evaluation reports unmarked open positions | Later evaluation has no unmarked positions |

## Gate Semantics

- `HEALTHY`: BUY and SELL continue through existing gates.
- `DEGRADED_SELL_ONLY`: BUY is rejected by `execution_state_gate`; SELL continues through existing gates.
- `HALTED`: Reserved for future central authority work. Current full-stop behavior remains the existing halt flag.
