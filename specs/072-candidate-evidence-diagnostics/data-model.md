# Data Model: Candidate Evidence Diagnostics

## CandidateEvidenceDiagnostic

- `code`: stable machine code for the dominant reason.
- `severity`: `info`, `warning`, or `blocked`.
- `retryable`: whether rerunning after safe remediation may produce a different outcome.
- `summary_ko`: operator-readable Korean summary.
- `evidence_source`: command, package, or executor surface that produced the diagnostic.
- `next_actions`: ordered list of safe `CandidateNextAction` entries.
- `details`: bounded, masked supporting data such as exit code, command surface, or excerpt.

Validation:
- Every pending or blocked result row must have at least one diagnostic.
- `blocked` diagnostics must not be retryable unless the package contract changes.
- Details must be JSON-serializable and secret-masked.

## CandidateNextAction

- `action_code`: stable action code.
- `summary_ko`: concise Korean action.
- `owner`: `automation`, `candidate_factory`, `operator`, or `future_spec`.
- `safe_to_auto_run`: whether a future automation may run this without live-money approval.

Validation:
- Actions must not call broker APIs or place orders.
- Actions must not change capital, whitelist/caps, live config, or sentinels.
- Each diagnostic must include at least one next action.

## CandidateResultRow Extension

Existing row fields remain unchanged:

- `candidate_id`
- `package_id`
- `package_kind`
- `status`
- `source_ref`
- strategy evidence fields or `factory_validation`
- `block_reason_ko`
- `output_summary_ko`
- `raw_metrics`
- `executions`

New additive fields:

- `diagnostics`: list of `CandidateEvidenceDiagnostic`
- `next_actions`: flattened safe action list for easy consumption
- `retryable`: true when at least one diagnostic is retryable and status is not `pass`

Validation:
- `pass` rows may omit diagnostics.
- `pending` and `blocked` rows must include diagnostics.
- Additive fields must not alter pass criteria.

## PromotionEvidencePatch Extension

Existing factory evidence fields remain unchanged. Additive fields:

- `factory_diagnostics`
- `factory_next_actions`
- `factory_retryable`

Validation:
- Strategy candidates still require `historical_backtest`, `recent_oos`, and `walk_forward` all `pass`.
- Non-strategy candidates still use `factory_validation`.
- Diagnostics may explain pending state but never create pass evidence.

## ExecutorRun Extension

Existing run fields remain unchanged. Additive fields:

- `diagnostic_counts`: mapping from diagnostic code to count.
- Markdown diagnostic summary uses the same counts and row diagnostics.

State transitions:

- `ready -> pass`: unchanged, diagnostics optional.
- `ready -> pending`: must include retryable or non-retryable diagnostic.
- `ready -> fail`: may include failure diagnostics when available.
- `ready -> blocked`: must include blocked diagnostic and no pass evidence.
