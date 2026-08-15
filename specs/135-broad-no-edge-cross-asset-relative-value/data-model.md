# Data Model: Broad No-Edge Cross-Asset Relative Value

## CrossAssetRelativeValueReport

- `schema_version`: Contract schema version.
- `contract_id`: Stable id `broad-no-edge-cross-asset-relative-value`.
- `completed_candidate_id`: `candidate-broad-no-edge-cross-asset-relative-value-experiment`.
- `next_candidate_id`: `candidate-broad-no-edge-tail-risk-convexity-experiment`.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `evidence_surfaces`: Parsed sidecar status rows.
- `forward_tracks`: Existing paper track summaries.
- `relative_value_lanes`: Proposed or waiting relative-value lanes.
- `cash_proxy_snapshot`: Treasury/FRED cash proxy evidence.
- `validation_gates`: PASS/WAIT/FAIL gates.
- `safety_boundary`: No-live invariants.

## RelativeValueLane

- `lane_id`: Stable lane id.
- `asset_pair`: Human-readable pair group.
- `status`: `PROPOSED`, `WAIT`, or `EXCLUDED`.
- `candidate_rule_ko`: Candidate rule in Korean.
- `required_inputs`: Evidence keys required by the lane.
- `exclusion_reason_ko`: Reason for wait or exclusion.

## ForwardTrack

- `key`, `label_ko`, `verdict`, `rank`, `n_obs`.
- `psr_vs_benchmark`, `sharpe`, `calmar`.
- `universe`: Symbols from forward paper evidence.
- `asset_classes`: Inferred classes such as equity, duration, commodity, credit, cash_proxy.

## CashProxySnapshot

- `available`: True when enough Treasury/FRED yield evidence exists.
- `evidence_items`: Public-data items used as cash proxy evidence.
- `summary_ko`: Human-readable status.

## ValidationGate

- `gate_id`: Stable gate id.
- `status`: PASS/WAIT/FAIL.
- `summary_ko`: Human-readable reason.
- `required_evidence`: Sidecar references.
