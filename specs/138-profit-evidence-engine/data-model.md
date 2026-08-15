# Data Model: Profit Evidence Engine

## ProfitCandidate

| Field | Type | Description |
|-------|------|-------------|
| `candidate_id` | string | Stable allocation/window identifier. |
| `allocation` | enum | `two_asset_equal`, `three_asset_fixed`, or `three_asset_inverse_vol`. |
| `trend_window_months` | integer | One of 6, 8, 10, 12. |
| `trial_index` | integer | Stable one-based trial index. |

## PerformanceSnapshot

| Field | Type | Description |
|-------|------|-------------|
| `n_months` | integer | Number of evaluated monthly returns. |
| `cagr_pct` | number | Cost-adjusted annual compound return. |
| `sharpe` | number | Annualized risk-adjusted return. |
| `max_drawdown_pct` | number | Maximum peak-to-trough loss. |
| `calmar` | number/null | CAGR divided by maximum drawdown. |

## TemporalSplit

| Field | Type | Description |
|-------|------|-------------|
| `development_start` | string | First selection month. |
| `development_end` | string | Last selection month. |
| `holdout_start` | string | First untouched evaluation month. |
| `holdout_end` | string | Last evaluation month. |
| `overlap_months` | integer | Must be zero. |

## HoldoutGate

| Field | Type | Description |
|-------|------|-------------|
| `gate_id` | string | `cagr`, `sharpe`, `drawdown`, or `neighbor_robustness`. |
| `passed` | boolean | Whether the candidate cleared the predeclared rule. |
| `candidate_value` | number/null | Candidate metric. |
| `benchmark_value` | number/null | Comparator metric. |
| `rule` | string | Stable human-readable threshold. |

## ForwardEvidence

| Field | Type | Description |
|-------|------|-------------|
| `track_key` | string | Expected `globalfixed` for the selected fixed allocation. |
| `present` | boolean | Whether a current row was found. |
| `n_obs` | integer/null | Forward observations. |
| `psr_vs_benchmark` | number/null | Current forward probability. |
| `verdict` | string/null | Current forward verdict. |
| `threshold` | number | Existing 0.95 gate. |

## ProfitEvidenceReport

| Field | Type | Description |
|-------|------|-------------|
| `status` | enum | `NO_HOLDOUT_EDGE`, `FORWARD_VALIDATION`, or `FORWARD_EDGE_READY`. |
| `historical_verdict` | enum | `HOLDOUT_EDGE` or `NO_HOLDOUT_EDGE`. |
| `trial_count` | integer | Exactly 12. |
| `selected_candidate` | ProfitCandidate | Development winner. |
| `development` | PerformanceSnapshot | Winner selection evidence. |
| `holdout` | PerformanceSnapshot | Untouched evaluation evidence. |
| `benchmark_holdout` | PerformanceSnapshot | Same-window benchmark. |
| `gates` | HoldoutGate[] | Complete pass/fail reasons. |
| `neighbors` | object[] | Adjacent window evidence. |
| `forward` | ForwardEvidence | Independent current observation. |
| `safety_invariants` | string[] | Explicit no-live boundary. |

## EvidenceAxis

| Field | Type | Description |
|-------|------|-------------|
| `historical_backtest` | enum | `pass`, `fail`, or `pending`. |
| `recent_oos` | enum | `pass`, `fail`, or `pending`. |
| `walk_forward` | enum | `pass`, `fail`, or `pending`. |
| `overall_status` | enum | `pass`, `fail`, or `pending`; mixed axes are pending. |
