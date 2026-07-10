# Data Model: PR/Merge Evidence Liveness Contract

## PRMergeEvidenceLivenessReport

- `schema_version`: Contract schema version.
- `run_id`: Local or workflow run id.
- `commit`: Source commit used for this report.
- `timestamp_utc`: Report creation time.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `completed_candidate_id`: `candidate-pr-merge-evidence-liveness-contract`.
- `next_candidate_id`: `candidate-worktree-concurrency-liveness-contract`.
- `evidence_surfaces`: Ordered evidence surface list.
- `merge_summary`: Latest main merge facts and PR number if available.
- `deploy_summary`: Supplied deploy-status observation classification and evidence boundary.
- `quality_gates`: PASS/WAIT/FAIL gates.
- `released_work_summary`: Completion marker state from released-work.
- `safety_invariants`: Read-only and money-path safety statements.

## EvidenceSurface

- `key`: Stable evidence key.
- `source_ref`: Repository path, sidecar reference, or supplied observation name.
- `present`: Whether the evidence was supplied or locally present.
- `parse_status`: `ok`, `present`, `missing`, or `malformed`.
- `summary_ko`: Korean operator-facing summary.

## QualityGate

- `gate_id`: Stable gate identifier.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Korean explanation.
- `evidence_keys`: Evidence keys that support this gate.

## State Transitions

1. Any `FAIL` gate means `overall_status=BLOCKED`.
2. No `FAIL` but one or more `WAIT` gates means `overall_status=OBSERVATION_WAIT`.
3. All gates `PASS` means `overall_status=CONTRACT_READY`.
4. released-work completion of `candidate-pr-merge-evidence-liveness-contract` advances autonomous-work to `candidate-worktree-concurrency-liveness-contract`.
