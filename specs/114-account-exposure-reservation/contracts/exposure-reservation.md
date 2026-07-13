# Contract: Exposure Reservation Boundary

## Allowed Effects

- Read current open orders from the local SQLite order ledger.
- Add open BUY notional to the exposure numbers passed to K1 gates.
- Keep in-run BUY reservation state inside `execute_rebalance` when no durable order row will be written.
- Reject or withhold unsafe BUY orders before broker submission.

## Forbidden Effects

- Do not place a real order as part of validation.
- Do not arm live sentinels.
- Do not change capital allocation, drawdown budget, whitelists, or configured caps.
- Do not treat open SELL orders as available exposure headroom.
- Do not remove or bypass `per_trade_cap_gate`, `per_symbol_cap_gate`, or `global_exposure_gate`.
- Do not change constitution or kernel manifest.

## Observable Contract

1. If open BUY notional plus the new BUY would exceed the global cap, the order outcome is `REJECTED_BY_GATE` with `global_exposure_gate`.
2. If earlier in-run BUY reservations plus the new BUY would exceed the global cap, the later order is not broker-submitted.
3. If no open BUY orders exist and the order is otherwise safe, existing router behavior remains unchanged.
