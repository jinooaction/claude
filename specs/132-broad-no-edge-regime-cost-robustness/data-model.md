# Data Model: Broad NO_EDGE Regime Cost Robustness

## Regime Cost Robustness Report

- `schema_version`: contract version.
- `experiment_id`: stable id `broad-no-edge-regime-cost-robustness`.
- `completed_candidate_id`: released-work marker `candidate-broad-no-edge-regime-cost-robustness-experiment`.
- `next_candidate_id`: next broad no-edge candidate `candidate-broad-no-edge-data-gap-audit`.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `regime_windows`: parsed regime-stratified strategy windows.
- `regime_metrics`: aggregate counts for windows, labels, pass/wait/stress labels.
- `execution_cost_snapshot`: broker and live gate context from execution-quality.
- `cost_stress_rows`: fixed stress rows for 10/25/50bp.
- `validation_gates`: pass/wait/fail checks.
- `safety_boundary`: no-live invariants.

## Regime Window

- `track_key`: normalized track key inferred from the section title.
- `label_ko`: human-readable section label.
- `join_rule`: regime label to return join rule.
- `total_return_days`: total joined return observations.
- `all_summary`: all-regime summary values.
- `regime_assessments`: label-level assessments.

## Regime Label Assessment

- `label`: regime label such as `CAUTION`, `RISK_ON`, or `RISK_OFF`.
- `n_days`: observations for the label.
- `total_return_pct`: cumulative return in that label.
- `sharpe`: optional Sharpe ratio.
- `max_drawdown_pct`: optional drawdown.
- `status`: `PASS`, `WAIT`, or `STRESS`.
- `reason_ko`: short explanation.

## Execution Cost Snapshot

- `overall_status`: execution-quality overall status.
- `monitor_verdict`: opportunity monitor verdict.
- `latest_signal`: latest live gate signal.
- `rejected_orders`: rejected order count.
- `parsed_broker_errors`: parsed broker error count.
- `broker_error_observation_rate`: parsed broker-error observation rate.
- `kis_msg_codes`: parsed KIS message codes.
- `smoke_state`: KIS smoke state.
- `smoke_error_rate`: KIS smoke error rate.
- `detail_ko`: plain-language summary.

## Cost Stress Row

- `stress_bps`: stress level.
- `stress_label`: mild, medium, or severe.
- `status`: `PROPOSED` or `WAIT`.
- `affected_tracks`: tracks to evaluate under this stress.
- `reason_ko`: why this stress row matters.

## Validation Gate

- `gate_id`: stable id.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: explanation.
- `required_evidence`: evidence refs that support the gate.
