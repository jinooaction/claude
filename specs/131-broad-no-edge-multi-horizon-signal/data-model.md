# Data Model: Broad NO_EDGE Multi-Horizon Signal

## MultiHorizonSignalReport

- `schema_version`: Report schema version.
- `run_id`, `commit`, `timestamp_utc`: Execution metadata.
- `experiment_id`: Stable value `broad-no-edge-multi-horizon-signal`.
- `completed_candidate_id`: Stable value `candidate-broad-no-edge-multi-horizon-signal-experiment`.
- `next_candidate_id`: Stable value `candidate-broad-no-edge-regime-cost-robustness-experiment`.
- `overall_status`: One of `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`.
- `headline_ko`: Human-readable Korean summary.
- `required_inputs`: Eight consumed sidecar refs.
- `evidence_surfaces`: Parsed sidecar statuses.
- `forward_signal_snapshots`: Current forward tournament tracks and derived signal/horizon coverage.
- `signal_horizon_metrics`: Current inferred signal families, holding periods, proposed/waiting/excluded counts, and data support.
- `proposed_signal_candidates`: No-live signal experiment candidates.
- `exclusion_criteria`: Deterministic reasons not to repeat already-failed or unsafe candidates.
- `money_state`: Read-only money path posture.
- `edge_autoarm_state`: Read-only edge-autoarm posture.
- `public_data_support`: Published macro evidence and warning summary.
- `regime_support`: Regime-stratify availability and coverage summary.
- `validation_gates`: Pass/wait/fail gates.
- `learning_summary`: Learning ledger and duplicate-memory posture.
- `released_work_summary`: Whether the completion marker is already visible.
- `safety_boundary`: No-live invariants.

## EvidenceSurface

- `key`: Stable sidecar key.
- `source_ref`: Branch and filename used by automation.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `summary_ko`: Short Korean parse summary.

## ForwardSignalSnapshot

- `key`: Forward track key.
- `label_ko`: Korean track label.
- `is_incumbent`: Whether the track is the current live-verification baseline.
- `verdict`: Current forward verdict.
- `comparability`: Observation readiness.
- `n_obs`, `min_obs`, `rank`: Forward evidence status.
- `universe`: Symbols reported by the forward row.
- `signal_families`: Inferred signal families, such as `trend`, `momentum`, `carry`, `quality`, `volatility`, or `unknown`.
- `holding_periods`: Inferred holding periods, such as `short`, `medium`, `long`, or `unknown`.
- `inference_notes_ko`: Short explanation of why the inference is conservative.

## SignalExperimentCandidate

- `candidate_key`: Stable candidate key.
- `title_ko`: Korean title.
- `signal_families`: Signal families covered by the candidate.
- `holding_periods`: Holding periods covered by the candidate.
- `status`: `PROPOSED`, `WAIT`, or `EXCLUDED`.
- `reason_ko`: Why the candidate widens the search surface.
- `separation_from_repeated_momentum_ko`: How it differs from a repeated single-horizon momentum test.
- `required_inputs`: Existing evidence refs that must be used before any later implementation.

## ExclusionCriterion

- `candidate_key`: Stable excluded idea key.
- `status`: `EXCLUDED`.
- `reason_ko`: Why the idea is not a valid next experiment in this slice.
- `covered_by_track`: Existing track key when applicable.

## State Transitions

- Missing or malformed critical evidence -> `BLOCKED`.
- Critical pipeline failure -> `BLOCKED`.
- Learning ledger suppresses current candidate -> `BLOCKED`.
- Evidence present but fewer than two separated candidates can be proposed -> `OBSERVATION_WAIT`.
- Evidence present and at least two separated no-live candidates exist -> `CONTRACT_READY`.
