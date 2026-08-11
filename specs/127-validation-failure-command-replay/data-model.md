# Data Model: Validation Failure Command Replay Contract

## Command Replay Contract

- `schema_version`: Contract schema version.
- `run_id`: Workflow or local run identifier.
- `commit`: Source commit.
- `timestamp_utc`: Report timestamp.
- `overall_status`: `CONTRACT_READY`, `WAITING_FOR_INPUT`, or `BLOCKED_UNSAFE_COMMAND`.
- `completed_candidate_id`: `candidate-broad-validation-failure-command-replay-contract`.
- `command_count`: Number of command rows.
- `package_count`: Number of packages represented.
- `replay_safe_count`: Number of commands classified as no-live replay-safe.
- `missing_execution_count`: Number of commands without observed exit/output evidence.
- `unsafe_command_count`: Number of commands blocked by safety classification.
- `safety_invariants`: No-live invariant list.
- `command_replay_contract`: Ordered command rows.

## Command Replay Row

- `candidate_id`: Source candidate id.
- `package_id`: Source package id.
- `package_kind`: Source package kind.
- `package_title_ko`: Optional Korean package title.
- `command_index`: One-based index within the package.
- `command`: Original validation command string.
- `command_digest`: Stable command fingerprint.
- `safe_to_replay`: Whether the command is inside the no-live validation allowlist.
- `replay_scope`: `allowlisted_no_live_validation` or `blocked`.
- `safety_reason_ko`: Human-readable safety explanation.
- `result_status`: Existing candidate result status if available.
- `observed_exit_code`: Existing execution exit code if available.
- `exit_code_evidence_status`: `present` or `missing_execution_evidence`.
- `stdout_excerpt`: Redacted limited stdout excerpt if available.
- `stderr_excerpt`: Redacted limited stderr excerpt if available.
- `output_digest`: Stable output fingerprint if output evidence exists.
- `diagnostic_codes`: Existing diagnostic code list.
- `retryable`: Existing retryable flag.
- `next_action_code`: Existing next safe action code if available.
- `next_action_ko`: Existing or default next action summary.
- `source_refs`: Source sidecar references.

## State Transitions

- Missing package or result evidence -> `WAITING_FOR_INPUT`.
- Target commands all no-live replay-safe -> `CONTRACT_READY`.
- Any target command unsafe -> `BLOCKED_UNSAFE_COMMAND`.
- `candidate-broad-validation-failure-command-replay-contract` released by spec 127 -> autonomous-work next child becomes `candidate-broad-validation-failure-data-readiness-contract`.
