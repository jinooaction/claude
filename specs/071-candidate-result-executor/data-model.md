# Data Model: Candidate Result Executor

## CandidatePackageInput

- `package_id`: stable package identifier from the factory.
- `candidate_id`: candidate identifier to merge evidence back into.
- `title_ko`: operator-readable Korean title.
- `package_kind`: one of the supported factory package kinds.
- `status`: factory package status, normally `ready`.
- `commands`: operator-readable command plan.
- `produces_evidence`: expected evidence keys.
- `safety_note_ko`: package safety statement.

Validation:
- Missing `package_id` or `candidate_id` blocks the package.
- Unknown `package_kind` blocks the package.
- Unsafe command tokens block the package before any execution.

## CandidateResultRow

- `candidate_id`: candidate identifier.
- `package_id`: package identifier.
- `package_kind`: package kind.
- `status`: `pass`, `fail`, `pending`, or `blocked`.
- `source_ref`: `candidate-result-executor:<package_id>`.
- `historical_backtest`: strategy-only evidence status.
- `recent_oos`: strategy-only evidence status.
- `walk_forward`: strategy-only evidence status.
- `factory_validation`: non-strategy validation status.
- `block_reason_ko`: Korean reason when blocked or pending.
- `output_summary_ko`: concise result explanation.
- `raw_metrics`: safe machine-readable metrics when available.

Validation:
- Strategy rows may include the three strategy evidence keys.
- Non-strategy rows use `factory_validation` and must not include strategy pass fields.
- Blocked rows must not include pass evidence.

## ExecutorRun

- `schema_version`
- `run_id`
- `commit`
- `timestamp_utc`
- `overall_status`
- `counts`
- `missing_inputs`
- `results`
- `blocked`

State transitions:
- `ready package -> pass`: all required evidence criteria pass.
- `ready package -> pending`: execution is safe but evidence is incomplete.
- `ready package -> fail`: execution is safe and evidence explicitly fails.
- `ready package -> blocked`: unsafe or unsupported package.
