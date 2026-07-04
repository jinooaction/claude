# Data Model: Forward Regime Edge Experiment

## ForwardRegimeEdgeExperimentReport

- `schema_version`: Report schema version.
- `experiment_id`: Stable id, `forward-regime-edge-experiment`.
- `completed_candidate_id`: `candidate-forward-regime-edge-experiment`.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `headline_ko`: Operator-readable status summary.
- `evidence_surfaces`: List of consumed sidecar evidence.
- `forward_tracks`: Forward tournament track snapshots.
- `money_state`: Top-level money-path status summary.
- `regime_context`: Optional current regime context extracted from existing sidecar evidence.
- `validation_gates`: Ordered gate list with pass, wait, or fail status.
- `next_observation_gate`: Observation count target and remaining observations.
- `safety_boundary`: No-live safety invariants.

## EvidenceSurface

- `key`: Stable sidecar key.
- `source_ref`: Branch/file reference used by automation.
- `parse_status`: `ok`, `present`, `missing`, or `malformed`.
- `summary_ko`: Short explanation of what was extracted.

## ForwardTrackSnapshot

- `key`: Track key from the forward tournament.
- `label_ko`: Operator-readable track label.
- `is_incumbent`: Whether the track is the current live-validation incumbent.
- `verdict`: `EDGE_CONFIRMED`, `NO_EDGE`, `INSUFFICIENT_DATA`, or null.
- `comparability`: `COMPARABLE`, `PREMATURE`, or `UNKNOWN`.
- `n_obs`, `min_obs`: Observation count and minimum comparable threshold.
- `rank`: Current deterministic tournament rank.
- `max_drawdown_pct`, `calmar`, `sharpe`: Optional metrics from the sidecar.

## MoneyState

- `status`: `PREVIEW_ONLY`, `REAL_ORDER_PATH_ARMED`, or unknown.
- `can_submit_real_orders`: Boolean if available.
- `stage`: Money-path stage if available.
- `detail_ko`: Operator-readable reason.

## ValidationGate

- `gate_id`: Stable id.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: One-line explanation.
- `required_evidence`: Sidecar refs or report fields needed for this gate.

## State Transitions

- Missing or malformed critical input -> `BLOCKED`.
- Critical pipeline liveness failure -> `BLOCKED`.
- All critical inputs parse but one or more forward tracks are premature -> `OBSERVATION_WAIT`.
- Critical inputs parse, no-live safety is intact, and forward tracks are comparable enough for evaluation -> `CONTRACT_READY`.

## Completed Candidate Marker

```yaml
completed_candidate_id: candidate-forward-regime-edge-experiment
```
