# Data Model: HANDOFF Truth Liveness Contract

## HANDOFF Truth Liveness Report

- `schema_version`: Stable report schema version.
- `run_id`: Local or workflow run identifier.
- `commit`: Source commit used for the report.
- `timestamp_utc`: Report creation time.
- `overall_status`: `CONTRACT_READY` when all gates pass, otherwise `BLOCKED`.
- `completed_candidate_id`: `candidate-handoff-truth-liveness-contract`.
- `next_candidate_id`: `candidate-pr-merge-evidence-liveness-contract`.
- `evidence_surfaces`: Repo-local files or controls the report relies on.
- `allowed_baselines`: Git-derived acceptable HANDOFF main row baselines.
- `handoff_summary`: Parsed and classified HANDOFF fact checker result.
- `quality_gates`: PASS/FAIL gates with Korean summaries and evidence keys.
- `released_work_summary`: Whether released-work has already closed this candidate.
- `safety_invariants`: Read-only and no-money-path invariants.

## Evidence Surface

- `key`: Stable evidence identifier.
- `source_ref`: Human-readable source reference.
- `present`: Whether the evidence file exists or checker is available.
- `parse_status`: `ok`, `present`, `missing`, or `malformed`.
- `summary_ko`: Operator-readable meaning.

## Allowed Main Baseline

- `kind`: `origin_main` or `handoff_only_first_parent`.
- `short_commit`: Short commit hash.
- `subject`: Commit subject.
- `reason_ko`: Why this baseline is accepted.

## Quality Gate

- `gate_id`: Stable gate identifier.
- `status`: `PASS` or `FAIL`.
- `summary_ko`: Operator-readable gate result.
- `evidence_keys`: Evidence surfaces used by the gate.

## Validation Rules

- `overall_status` is `CONTRACT_READY` only if every quality gate is `PASS`.
- Missing or unreadable `HANDOFF.md` is always `BLOCKED`.
- A HANDOFF main row must match at least one allowed baseline.
- Optional expected rows must match when the caller supplies them.
- Safety invariants are always reported and must remain read-only.
