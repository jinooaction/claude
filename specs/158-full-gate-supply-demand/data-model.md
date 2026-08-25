# Data Model: Full-Gate Audit and Commodity Supply-Demand

## FullGateControlResult

- `control_id`, `objective`, `window`, `observations`, `cost_bps`
- `psr`, `annual_excess_return`, `incumbent_correlation`
- `incumbent_sharpe`, `blend_sharpe`, `blend_sharpe_improvement`
- `incumbent_max_drawdown_pct`, `blend_max_drawdown_pct`
- `gates[]`, `passed`, `fingerprint`

## EiaSupplyDemandObservation

- `series_id`: one fixed EIA identity
- `period_end`, `available_date=period_end+5 days`
- `value`, `unit`, `source_digest`
- Validation: finite, positive, unique `(series_id, period_end)`.

## CommoditySupplyDemandPolicy

- `family`: inventory draw, demand growth, refinery pull, synchronized balance
- `normalization_weeks`: 52 or 104
- `max_commodity_weight`: 0.5 or 1.0
- `candidate_id`, `trial_index`, `strategy_fingerprint`

## CommoditySupplyDemandBundle

- Monthly `dates`, GSG `fund_levels`, DGS3MO `cash_rates`
- Signal maps by normalization window
- Source coverage, freshness, lag, revision disclosure, and content hashes

## CommoditySupplyDemandDecision

- 96-month development selection, one-month embargo, untouched holdout
- DSR/PBO diagnostics, live and paper gates, selected identifiers
- 688 prior plus 16 current audit records
- Safety state: whitelist false, deployment config null unless full pass, no broker boundary
