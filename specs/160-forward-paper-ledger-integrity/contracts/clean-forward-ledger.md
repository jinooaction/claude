# Contract: Clean Forward Ledger

## Snapshot Interlock

For a command equivalent to:

```text
nav-snapshot --mode paper --capital C --snapshot
```

let `cash = C + cumulative_sell_cash - cumulative_buy_cash`.

- `cash >= -0.01`: exit 0; output includes `capital_basis_usd`, `ledger_cash_nonnegative=true`, and `measurement_valid=true`; snapshot may append.
- `cash < -0.01`: exit nonzero; stderr names `negative paper cash`; no snapshot is appended.

Live mode and paper mode without a capital basis preserve their existing contract.

## Epoch Bindings

| Track | Active DB |
|---|---|
| trend | `data/forward_v2_trend.db` |
| notrend | `data/forward_v2_notrend.db` |
| rmbeta | `data/forward_v2_rmbeta.db` |
| multiasset | `data/forward_v2_multiasset.db` |
| global | `data/forward_v2_global.db` |
| globalfixed | `data/forward_v2_globalfixed.db` |
| wide | `data/forward_v2_wide.db` |

No consumer may fall back to the corresponding legacy path.

## Promotion Contract

Legacy forward values observed on 2026-08-25, including `multiasset` PSR 0.806220 and `globalfixed` PSR 0.728797, are forensic evidence only. They cannot satisfy exploration, full edge, reassignment, or capital-ladder gates.
