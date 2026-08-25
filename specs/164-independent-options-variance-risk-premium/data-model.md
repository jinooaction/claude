# Data Model: Independent Options Variance Risk Premium

## OptionsPremiumObservation

| Field | Type | Constraint |
|---|---|---|
| `date` | date | Unique trading date |
| `put_level` | decimal | Positive Cboe PUT index level |
| `vix_close` | decimal | Positive annualized implied volatility percentage |
| `market_return` | decimal | Fama-French daily broad-market total return |
| `cash_return` | decimal | Daily or monthly risk-free return |
| `known_at` | timestamp/date | No later than signal month end |
| `source_digest` | string | `sha256:` content identity |

## VarianceRiskPremiumSnapshot

| Field | Type | Constraint |
|---|---|---|
| `feature_month` | month | Month containing known inputs |
| `target_month` | month | Exactly the following month |
| `implied_variance` | decimal | `(VIX / 100)^2` |
| `realized_variance` | decimal | Daily market variance annualized by 252 |
| `variance_premium` | decimal | Implied minus realized variance |
| `equity_trend` | decimal | Frozen 6/12-month market total return |
| `market_drawdown` | decimal | Drawdown known at feature month end |
| `vix_shock` | boolean | Current VIX above trailing mean plus one standard deviation |
| `put_excess_lag` | decimal | Prior PUT return minus cash, never target return |

## OptionsPremiumPolicy

| Field | Type | Constraint |
|---|---|---|
| `family` | enum | `passive_put`, `positive_vrp`, `tail_guarded`, `ridge_forecast` |
| `horizon_months` | integer/null | 6 or 12 for dynamic families; null for passive |
| `max_put_weight` | decimal | Passive 0.25/0.50/0.75/1.00; dynamic 0.50/1.00 |
| `ridge_alpha` | decimal/null | Exactly 10 for ridge |
| `minimum_labels` | integer/null | Exactly 60 for ridge |
| `candidate_id` | string | Stable hash-derived identity |
| `strategy_fingerprint` | string | Unique immutable `sha256:` identity |

## CandidateEvaluation

| Field | Type | Constraint |
|---|---|---|
| `development_metrics` | object | Middle-cost return, Sharpe, drawdown, expected shortfall |
| `holdout_metrics` | object | All three annual and turnover cost combinations |
| `standalone_live_lane` | gate set | Five boolean gates |
| `standalone_paper_lane` | gate set | Five boolean gates |
| `timing_enhancement_lane` | gate set/null | Dynamic candidates only; non-blocking for standalone |
| `active_fraction` | decimal | Fraction of months with positive PUT exposure |
| `promotion_allowed` | boolean | True only for frozen winner after all research gates; still blocked by live parity |

## PriorAdoptionAudit

| Field | Type | Constraint |
|---|---|---|
| `family` | string | Released strategy family identity |
| `frozen_candidate_id` | string/null | Original development winner |
| `original_verdict` | string | Preserved verbatim |
| `classification` | enum | Negative, uncertain, post-hoc, objective-corrected, forward-missing, parity-missing |
| `retroactive_promotion_allowed` | boolean | Always false |
| `evidence_source_digest` | string | Hash of consumed decision JSON |

## OptionsPremiumDecision

| Field | Type | Constraint |
|---|---|---|
| `verdict` | enum | One of the five FR-019 verdicts |
| `criterion_diagnosis` | string | Candidate, gate, or reference explanation |
| `development_winner` | string | Chosen before holdout inspection |
| `split` | object | Exactly 84 development months, one embargo month, and at least 120 holdout months |
| `reference_control` | object | Full PUT and mean-zero null results |
| `objective_gate_calibration` | object | Null, planted detection, correct selection |
| `prior_adoption_audit` | list | No retroactive promotion |
| `live_parity` | object | Mandatory fail-closed blockers |

## Relationships

1. Daily observations aggregate into one monthly variance snapshot.
2. One policy consumes the same frozen snapshots and emits three cost cases.
3. Development evaluations select one candidate; only that identity reaches holdout gates.
4. Prior adoption records explain historical non-adoption but cannot alter candidate returns or verdicts.
5. A research decision remains separated from any broker, order, capital, or whitelist entity.
