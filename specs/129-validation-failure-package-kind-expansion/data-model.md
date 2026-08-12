# Data Model: Validation Failure Package-Kind Expansion Contract

## Package-Kind Expansion Contract

- `schema_version`: contract schema version.
- `run_id`, `commit`, `timestamp_utc`: reproducibility metadata.
- `overall_status`: `CONTRACT_READY` or `WAITING_FOR_EVIDENCE`.
- `completed_candidate_id`: `candidate-broad-validation-failure-package-kind-expansion-contract`.
- `package_count`, `bucket_count`, `retryable_count`, `command_count`, `execution_evidence_count`: aggregate counts.
- `missing_inputs`: missing required input surfaces.
- `safety_invariants`: no-live boundaries.
- `package_kind_expansion_contract`: package-kind buckets.

## Package-Kind Bucket

- `package_kind`: package kind such as `strategy_backtest` or `portfolio_backtest`.
- `domain_keys`: domains represented by packages in the bucket.
- `package_count`, `retryable_count`, `command_count`, `execution_evidence_count`: bucket counts.
- `failure_codes`: stable diagnostic codes such as `execution_failed`.
- `result_statuses`: result statuses observed for the bucket.
- `review_axes`: dimensions the next worker must inspect.
- `experiment_axes`: deterministic no-live follow-up axes.
- `metric_summary`: parsed metric range and text hints from existing result evidence.
- `package_refs`: package-level traceability rows.
- `bucket_status`: `READY_FOR_AXIS_EXPANSION` or `WAITING_FOR_EVIDENCE`.
- `next_action_code`, `next_action_ko`: deterministic next action.

## Package Failure Ref

- `candidate_id`, `package_id`, `package_kind`, `domain_key`, `title_ko`: package identity.
- `package_status`, `result_status`: source package/result statuses.
- `diagnostic_codes`: stable diagnostic codes from promotion patch evidence.
- `next_action_codes`: safe next actions already emitted by the factory.
- `retryable`: whether the factory marked the package retryable.
- `command_count`, `execution_count`: planned and observed evidence counts.
- `command_digests`: stable command references.
- `metric_highlights`: parsed metrics such as `segments_strategy_wins`, Sharpe values, PSR/DSR, and verdict.
- `text_hints`: limited stdout/stderr hints for non-JSON evidence.
- `source_refs`: sidecar references.

## Experiment Axis

- `axis_key`: stable key such as `strategy_family`, `portfolio_design`, `holding_period`, or `evidence_output`.
- `label_ko`: operator-readable Korean label.
- `reason_ko`: why this axis is the next safe no-live review direction.
- `applies_to_package_kinds`: package kinds covered by this axis.

## State Transition

- `candidate-broad-validation-failure-data-readiness-contract` released by spec 128 -> autonomous-work next child becomes `candidate-broad-validation-failure-package-kind-expansion-contract`.
- `candidate-broad-validation-failure-package-kind-expansion-contract` released by this spec -> autonomous-work next child becomes `candidate-broad-validation-failure-promotion-recheck-contract`.
