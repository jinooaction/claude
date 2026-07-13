# Contract: Degraded Execution State

## Scope

The degraded execution state is an account-safety gate. It is allowed to reduce order eligibility, never to increase it.

## Inputs

- Existing `orders` rows.
- Existing `reconciliation_runs` rows.
- Optional worker runtime blockers from the current process.

## Outputs

```json
{
  "status": "DEGRADED_SELL_ONLY",
  "reasons": [
    {
      "code": "fill_sync_error",
      "detail": "live fill sync failed while open orders exist"
    }
  ]
}
```

## Required Behavior

- BUY orders in `DEGRADED_SELL_ONLY` are rejected by `execution_state_gate`.
- SELL orders in `DEGRADED_SELL_ONLY` are not rejected by this gate.
- Broker order submission is never attempted for BUY orders rejected by this gate.
- The gate must append the existing `ORDER_REJECTED_BY_GATE` audit event, not introduce a parallel audit path.
- Existing halt behavior remains authoritative and can still block all orders.

## Forbidden Behavior

- Do not set `armed: true`.
- Do not switch `AUTO_INVEST_MODE` to live.
- Do not submit real orders as part of validation.
- Do not change capital, whitelist, configured cap values, loss budgets, live sentinels, secrets, constitution, or kernel manifest.
- Do not implement cross-process locks or central `ExecutionAuthority` in this spec.
