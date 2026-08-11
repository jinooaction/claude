# Data Model: Broad NO_EDGE Asset Universe Rotation

## AssetUniverseRotationReport

- `schema_version`: Report schema version.
- `run_id`, `commit`, `timestamp_utc`: Execution metadata.
- `experiment_id`: Stable value `broad-no-edge-asset-universe-rotation`.
- `completed_candidate_id`: Stable value `candidate-broad-no-edge-asset-universe-rotation-experiment`.
- `next_candidate_id`: Stable value `candidate-broad-no-edge-multi-horizon-signal-experiment`.
- `overall_status`: One of `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`.
- `headline_ko`: Human-readable Korean summary.
- `required_inputs`: Seven consumed sidecar refs.
- `evidence_surfaces`: Parsed sidecar statuses.
- `forward_universe_snapshots`: Current forward tournament tracks and derived asset buckets.
- `asset_universe_metrics`: Current tested bucket count, incumbent buckets, wide-track status, proposed/excluded counts, and data support.
- `proposed_rotation_candidates`: No-live defensive rotation candidates.
- `exclusion_criteria`: Deterministic reasons not to repeat already-failed or unsafe candidates.
- `money_state`: Read-only money path posture.
- `edge_autoarm_state`: Read-only edge-autoarm posture.
- `public_data_support`: Published macro evidence and warning summary.
- `validation_gates`: Pass/wait/fail gates.
- `learning_summary`: Learning ledger and duplicate-memory posture.
- `released_work_summary`: Whether the completion marker is already visible.
- `safety_boundary`: No-live invariants.

## EvidenceSurface

- `key`: Stable sidecar key.
- `source_ref`: Branch and filename used by automation.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `summary_ko`: Short Korean parse summary.

## ForwardUniverseSnapshot

- `key`: Forward track key.
- `label_ko`: Korean track label.
- `is_incumbent`: Whether the track is the current live-verification baseline.
- `verdict`: Current forward verdict.
- `comparability`: Observation readiness.
- `n_obs`, `min_obs`, `rank`: Forward evidence status.
- `universe`: Symbols reported by the forward row.
- `asset_buckets`: Derived asset buckets for the universe.

## DefensiveRotationCandidate

- `candidate_key`: Stable candidate key.
- `title_ko`: Korean title.
- `asset_bucket`: Target defensive bucket.
- `candidate_symbols`: Candidate symbols to consider in no-live design.
- `status`: `PROPOSED`, `WAIT`, or `EXCLUDED`.
- `reason_ko`: Why the candidate widens the search surface.
- `separation_ko`: How it differs from already-failed direct wide expansion.
- `required_evidence`: Existing evidence refs that must be used before any later implementation.

## ExclusionCriterion

- `candidate_key`: Stable excluded idea key.
- `status`: `EXCLUDED`.
- `reason_ko`: Why the idea is not a valid next experiment in this slice.
- `covered_by_track`: Existing track key when applicable.

## State Transitions

- Missing or malformed critical evidence -> `BLOCKED`.
- Critical pipeline failure -> `BLOCKED`.
- Learning ledger suppresses current candidate -> `BLOCKED`.
- Evidence present but no separated candidate can be proposed -> `OBSERVATION_WAIT`.
- Evidence present and separated no-live candidates exist -> `CONTRACT_READY`.
