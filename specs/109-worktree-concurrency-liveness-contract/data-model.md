# Data Model: Worktree Concurrency Liveness Contract

## WorktreeConcurrencyLivenessReport

- `schema_version`: Report schema version.
- `run_id`: Workflow or local run identifier.
- `commit`: Source commit used to generate the report.
- `timestamp_utc`: UTC report time.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `completed_candidate_id`: `candidate-worktree-concurrency-liveness-contract`.
- `next_candidate_id`: `candidate-agent-harness-regression-liveness-contract`.
- `evidence_surfaces`: List of source and runtime evidence surfaces.
- `guard_behavior_summary`: Synthetic guard outcome map.
- `runtime_state_summary`: Optional local guard output and runtime directory summary.
- `quality_gates`: PASS/WAIT/FAIL gate list.
- `released_work_summary`: Completion marker status.
- `safety_invariants`: Read-only and no-money-path invariants.

## EvidenceSurface

- `key`: Stable evidence key.
- `source_ref`: File path, runtime path, sidecar reference, or supplied observation label.
- `present`: Whether the surface was present.
- `parse_status`: `ok`, `present`, `missing`, or `malformed`.
- `summary_ko`: Human-readable Korean summary.

## QualityGate

- `gate_id`: Stable gate key.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Korean decision explanation.
- `evidence_keys`: Related evidence keys.

## GuardBehaviorSummary

- `clean_check`: Expected `OK`.
- `conflict_check`: Expected `WARN`.
- `conflict_pre_commit`: Expected `BLOCK`.
- `conflict_pre_push`: Expected `BLOCK`.
- `main_branch_pre_commit`: Expected `BLOCK`.
- `main_push_pre_push`: Expected `BLOCK`.

## ReleasedWorkSummary

- `parse_status`: released-work parse status.
- `completed_candidate_id`: This feature's candidate marker.
- `completed_candidate_released`: Whether released-work consumed the marker.
- `released_count`: Number of released candidate IDs found.

## Candidate Markers

```text
completed_candidate_id: candidate-worktree-concurrency-liveness-contract
next_candidate_id: candidate-agent-harness-regression-liveness-contract
```
