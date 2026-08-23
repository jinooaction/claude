# Contract: Treasury Carry Factory Evidence

## Inputs

- Five official yield CSV files: `fred/DGS3MO.csv`, `fred/DGS2.csv`, `fred/DGS5.csv`, `fred/DGS10.csv`, `fred/DGS30.csv`.
- Previous complete factory JSON containing exactly 512 unique trial fingerprints and ten segment scores per trial.
- Existing Shiller stock/bond rows and gold monthly levels for the incumbent diversification comparison.
- Code commit and UTC execution timestamp.

## Output JSON

Required top-level keys:

```text
schema_version, batch_id, timestamp_utc, code_commit,
treasury_data_fingerprint, candidate_count, complete_trial_count,
prior_trial_count, current_trial_count, multiplicity_trial_count,
unique_trial_fingerprint_count, candidates, trial_records,
treasury_data, research_live_parity, live_treasury_evidence,
decision, treasury_benchmark, incumbent_benchmark, blend, safety
```

## Decision Contract

`decision.verdict` is `FACTORY_EDGE` only when all gate rows pass. In that state
`selected_candidate_id`, `selected_strategy_fingerprint`, and `selected_deploy_config` are non-null.
For every other state all three are null and `research_canary_eligible=false`.

## Required Gates

- exact 64 current complete trials
- exact 512 prior complete unique trials
- exact 576 cumulative unique fingerprints
- data completeness, publication safety, and latest freshness
- at least 120 development and 120 holdout months
- one full monthly embargo between development and evaluated holdout returns
- research/order target-weight equality
- DSR >= 0.95, PBO <= 0.10, PSR >= 0.95
- ten-segment win rate >= 0.60
- candidate Sharpe >= Treasury ladder Sharpe + 0.20
- candidate Calmar above Treasury ladder
- candidate max drawdown <= 80% of Treasury ladder max drawdown
- positive total return at 50 basis points turnover cost
- correlation with incumbent < 0.80
- 80/20 blend Sharpe >= incumbent Sharpe + 0.05
- 80/20 blend max drawdown <= incumbent max drawdown

## Failure Contract

Missing, stale, malformed, partial, duplicate, mismatched, future-dated, or non-long-only evidence
must fail before broker contact. The factory itself never submits orders or changes capital,
whitelist, caps, live arming, secrets, constitution, or kernel.
