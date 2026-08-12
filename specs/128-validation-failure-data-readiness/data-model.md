# Data Model: Validation Failure Data Readiness Contract

## Data Readiness Contract

- `schema_version`: contract schema version.
- `run_id`, `commit`, `timestamp_utc`: reproducibility metadata.
- `overall_status`: `CONTRACT_READY`, `WAITING_FOR_EVIDENCE`, or `BLOCKED_DATA_INPUT`.
- `completed_candidate_id`: `candidate-broad-validation-failure-data-readiness-contract`.
- `package_count`, `surface_count`, `data_ready_count`, `waiting_count`, `blocked_count`: aggregate counts.
- `public_data_summary`: research-only public-data sidecar summary.
- `regime_stratify_summary`: regime-stratify sidecar summary.
- `missing_inputs`: missing required input surfaces.
- `safety_invariants`: no-live boundaries.
- `data_readiness_contract`: package rows.

## Data Readiness Row

- `candidate_id`, `package_id`, `package_kind`, `package_title_ko`: package identity.
- `readiness_status`: package-level PASS/WAIT/FAIL classification.
- `data_missing_causes`: stable cause codes.
- `execution_count`: number of executions present for the package.
- `portfolio_paths`, `history_roots`, `manifest_dataset_keys`: package data surfaces.
- `observation_window`: earliest and latest observed portfolio-walk-forward evaluation dates.
- `latest_data_session`, `max_data_age_days`, `data_staleness_values`: observed data freshness.
- `surface_count`: number of portfolio data surfaces.
- `data_surfaces`: per-command portfolio surfaces.
- `public_data_status`, `regime_stratify_status`: sidecar context.
- `next_action_code`, `next_action_ko`: deterministic next action.

## Data Surface

- `command_index`, `command_digest`: stable command reference.
- `portfolio_path`: portfolio TOML path from command.
- `history_root`: command history root.
- `manifest_dataset_key`, `manifest_history_root`, `manifest_db_path`: manifest match.
- `portfolio_toml_exists`, `history_root_matches_manifest`: repository and manifest checks.
- `execution_exit_code`: observed exit code if present.
- `data_newest_session`, `data_age_days`, `data_staleness`: freshness evidence from stdout JSON.
- `eval_window_start`, `eval_window_end`, `n_segments`: observation period evidence.
- `surface_status`: `PASS_DATA_READY`, `WAITING_FOR_EVIDENCE`, or `BLOCKED_DATA_INPUT`.
- `causes`: stable cause codes.

## State Transition

- `candidate-broad-validation-failure-command-replay-contract` released by spec 127 -> autonomous-work next child becomes `candidate-broad-validation-failure-data-readiness-contract`.
- `candidate-broad-validation-failure-data-readiness-contract` released by this spec -> autonomous-work next child becomes `candidate-broad-validation-failure-package-kind-expansion-contract`.
