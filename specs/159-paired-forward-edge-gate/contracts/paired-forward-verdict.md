# Contract: Paired Forward Verdict 1.2

## Required output fields

```json
{
  "schema_version": "1.2",
  "significance_method": "paired_active_return_psr_v1",
  "verdict": "EDGE_CONFIRMED | NO_EDGE | INSUFFICIENT_DATA",
  "n_obs": 48,
  "strategy_sharpe_annual": "1.522283",
  "benchmark_sharpe_annual": "...",
  "active_information_ratio_annual": "...",
  "psr_vs_benchmark": "...",
  "dsr": null,
  "dsr_threshold": "0.95",
  "has_benchmark": true
}
```

`psr_vs_benchmark` means the PSR of aligned active returns against zero. It no longer means PSR of the strategy return series against an estimated benchmark Sharpe treated as fixed.

## Failure contract

- Unequal curve or return lengths -> `INSUFFICIENT_DATA`
- Fewer observations than configured minimum -> `INSUFFICIENT_DATA`
- Zero active-return variance -> `INSUFFICIENT_DATA`
- Missing method in downstream promotion evidence -> not eligible

## Compatibility

Absolute strategy and benchmark metrics and existing field names remain for readers. Schema 1.1 or a missing method may be displayed historically but cannot be used for a new paired-method promotion.
