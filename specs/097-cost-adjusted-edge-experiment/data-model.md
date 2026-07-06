# Data Model: Cost-Adjusted Edge Experiment

## CostAdjustedEdgeExperimentReport

- `schema_version`: report schema version.
- `run_id`, `commit`, `timestamp_utc`: reproducibility metadata.
- `experiment_id`: `cost-adjusted-edge-experiment`.
- `completed_candidate_id`: `candidate-cost-adjusted-edge-experiment`.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `headline_ko`: operator-readable Korean summary.
- `required_inputs`: source refs for the six consumed sidecars.
- `evidence_surfaces`: parse status for each input.
- `forward_tracks`: normalized forward track snapshots.
- `execution_cost`: execution-quality summary.
- `cost_adjusted_candidates`: cost-stressed track candidates.
- `cost_metrics`: aggregate count and best/worst stress metrics.
- `money_state`: no-live money-path snapshot.
- `validation_gates`: machine-readable gate outcomes.
- `learning_summary`: current candidate duplication/suppression state.
- `released_work_summary`: whether the completion marker is visible.
- `safety_boundary`: read-only invariants.

## ForwardCostTrack

- `key`, `label_ko`, `is_incumbent`
- `verdict`, `comparability`
- `n_obs`, `min_obs`, `rank`
- `total_return_pct`, `max_drawdown_pct`
- `universe`

## CostAdjustedCandidate

- `track_key`, `label_ko`, `is_incumbent`
- `base_total_return_pct`
- `stress_bps`
- `stress_cost_pct`
- `cost_adjusted_return_pct`
- `status`: `PROVISIONAL`, `WAIT`, or `NOT_AVAILABLE`
- `reason_ko`

## ExecutionCostSnapshot

- `overall_status`
- `monitor_verdict`
- `latest_signal`
- `cumulative_pnl_usd`
- `rejected_orders`
- `parsed_broker_errors`
- `broker_error_observation_rate`
- `kis_msg_codes`
- `smoke_state`, `smoke_error_rate`
- `cost_basis_complete`
- `detail_ko`

## ValidationGate

- `gate_id`
- `status`: `PASS`, `WAIT`, or `FAIL`
- `summary_ko`
- `required_evidence`

