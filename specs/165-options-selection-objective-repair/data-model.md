# Data Model: Options Selection and Objective Repair

## WputHistory

- `source_url`: canonical Cboe WPUT CSV URL
- `observations`: strictly increasing `(date, index_level)` pairs
- `continuous_start`: `2006-01-31`
- `freshness_days`: age of the latest observation
- Invariants: exact `DATE,WPUT` header, no duplicate dates, positive levels, and a continuous-start observation.

## OptionsPremiumBundle

- Existing PUT, VIX, French-factor, and FRED series
- `wput_factors`: month-end WPUT total-return factors aligned to the common calendar
- Invariants: all factor arrays have equal length and all required public sources pass schema and freshness checks.

## NestedFold

- `outer_index`, `outer_train_start`, `outer_train_end`, `outer_embargo`, `outer_test_start`, `outer_test_end`
- `inner_folds`: expanding training and strictly later validation intervals fully contained in the outer training interval
- Invariants: `inner_validation_end < outer_test_start`; embargo months are not used for training or scoring.

## SelectionScore

- `candidate_id`
- `worst_inner_cash_excess_sharpe`
- `median_inner_cash_excess_sharpe`
- `median_inner_equity_sharpe_improvement`
- `median_inner_tail_advantage`
- `selection_key`
- Invariants: all statistics use PUT only; ties end with stable candidate ID ordering.

## ObjectiveLane

- `lane_id`: `premium_existence`, `portfolio_adoption`, or `timing_value`
- `put_metrics`, `wput_metrics`
- `gate_results`, `passed`
- `diagnostic_only=true`
- `promotion_eligible=false`
- Invariants: WPUT uses the exact candidate IDs and monthly weights selected from PUT outer-training data.

## SystemReviewFinding

- `severity`: `P0` through `P3`
- `domain`: one of seven review domains
- `finding`, `evidence`, `money_path_effect`, `remediation`, `status`
- Invariants: readiness scores cannot exceed the weakest mandatory gate and unverified claims are explicitly marked.
