# Data Model: Uncertainty-Aware ML Edge Ensemble

## MonthlyPanelRow

- `date`, `asset`, `features`, `target_date`, `target_return`
- Validation: finite lagged features, target strictly after feature date, unique date/asset.

## FoldResult

- `fold_id`, `train_start`, `train_end`, `purge_end`, `test_start`, `test_end`
- `train_rows`, `test_rows`, model validation errors, predictions, realized returns.
- Validation: every training label date is earlier than the test start.

## AllocationDecision

- `date`, per-asset prediction, uncertainty, lower bound, weight, cash weight, turnover.
- Validation: weights are non-negative, each <= 0.40, sum <= 0.99.

## CostScenario

- `cost_bps`, monthly net factors, total return, CAGR, Sharpe, Calmar, max drawdown.

## MLEdgeReport

- input/model/feature fingerprints, folds, allocations, model metrics, cost scenarios, benchmarks, regime slices, significance, gates, verdict.
- States: `BLOCKED_DATA` -> `BLOCKED_MODEL` -> `NO_EDGE` or `ML_EDGE_CANDIDATE_READY`.

## CandidatePackage

- candidate id, kind `strategy_backtest`, verdict, replay command, evidence references, exact fingerprints, safety declaration.
- It is advisory research evidence and cannot mutate live state.
