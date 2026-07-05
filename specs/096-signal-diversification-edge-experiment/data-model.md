# Data Model: Signal Diversification Edge Experiment

## SignalDiversificationEdgeExperimentReport

- `schema_version`: Report schema version.
- `run_id`, `commit`, `timestamp_utc`: Execution metadata.
- `experiment_id`: Stable value `signal-diversification-edge-experiment`.
- `completed_candidate_id`: Stable value `candidate-signal-diversification-edge-experiment`.
- `overall_status`: One of `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`.
- `headline_ko`: Human-readable Korean summary.
- `required_inputs`: Five consumed sidecar refs.
- `evidence_surfaces`: Parsed sidecar statuses.
- `signal_families`: Grouped forward tracks by signal family.
- `proposed_signal_candidates`: Candidate signal ideas that widen the no-live search surface.
- `diversification_metrics`: Family count, concentration, incumbent overlap, observation readiness.
- `money_state`: Read-only money path posture.
- `validation_gates`: Pass/wait/fail gates.
- `learning_summary`: Learning ledger and duplicate-memory posture.
- `released_work_summary`: Whether the completion marker is already visible.
- `safety_boundary`: No-live invariants.

## EvidenceSurface

- `key`: Stable sidecar key.
- `source_ref`: Branch and filename used by automation.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `summary_ko`: Short Korean parse summary.

## SignalFamilySnapshot

- `family_key`: Stable family key.
- `label_ko`: Korean family label.
- `track_keys`: Forward track keys in the family.
- `track_count`: Number of tracks in the family.
- `incumbent_present`: Whether the live-verification incumbent is in this family.
- `max_n_obs`: Highest observation count among tracks in the family.
- `verdicts`: Distinct verdict values in the family.

## SignalCandidate

- `candidate_key`: Stable candidate key.
- `family_key`: Target signal family.
- `title_ko`: Korean candidate title.
- `reason_ko`: Why this candidate widens the search surface.
- `required_inputs`: Existing no-live evidence refs.
- `overlap_with_incumbent`: Universe overlap ratio when calculable.
- `status`: `PROPOSED`, `WAIT`, or `BLOCKED`.

## DiversificationMetrics

- `family_count`: Number of observed signal families.
- `largest_family_key`: Family with the most tracks.
- `largest_family_share`: Largest family share of observed tracks.
- `incumbent_family_key`: Family containing the incumbent track.
- `lowest_overlap_candidate_key`: Proposed candidate with lowest universe overlap to incumbent.
- `forward_comparable_count`: Comparable forward tracks from the leaderboard.
- `max_n_obs`, `target_min_obs`, `remaining_observations`: Observation readiness.

## ValidationGate

- `gate_id`: Stable gate id.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Korean explanation.
- `required_evidence`: Evidence refs needed by the gate.

## State Transitions

- Missing or malformed critical evidence -> `BLOCKED`.
- Critical pipeline failure -> `BLOCKED`.
- Evidence present and proposed low-overlap candidates exist, but forward observations remain premature -> `OBSERVATION_WAIT`.
- Evidence present and the contract can be evaluated without live-money action -> `CONTRACT_READY`.
