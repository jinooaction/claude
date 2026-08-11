# Contract: Broad NO_EDGE Asset Universe Rotation

completed_candidate_id: candidate-broad-no-edge-asset-universe-rotation-experiment
next_candidate_id: candidate-broad-no-edge-multi-horizon-signal-experiment

## Probe Manifest

`scripts/broad_no_edge_asset_universe_rotation_probe.py --manifest` emits:

```text
rebalance-paper-forward	automation/rebalance-paper-forward-last-run	LAST_RUN.md
money-path	automation/money-path-last-run	LAST_RUN.md
edge-autoarm	automation/edge-autoarm-last-run	LAST_RUN.md
public-data	automation/public-data	LAST_RUN.md
released-work	automation/released-work-last-run	released_work.json
evolution-ledger	automation/autonomous-evolution-last-run	learning_ledger.json
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
```

## JSON Report

Required top-level fields:

- `schema_version`
- `run_id`
- `commit`
- `timestamp_utc`
- `experiment_id`
- `completed_candidate_id`
- `next_candidate_id`
- `overall_status`
- `headline_ko`
- `required_inputs`
- `evidence_surfaces`
- `forward_universe_snapshots`
- `asset_universe_metrics`
- `proposed_rotation_candidates`
- `exclusion_criteria`
- `money_state`
- `edge_autoarm_state`
- `public_data_support`
- `validation_gates`
- `learning_summary`
- `released_work_summary`
- `safety_boundary`

## Safety Boundary

The report is read-only and must include:

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no secret read/write
- no external paid service
- no constitution/kernel change
- experiment contract only

## Completion Behavior

When released-work scans this spec, it must record `candidate-broad-no-edge-asset-universe-rotation-experiment` as released. Autonomous-work should then advance the broad no-edge frontier to `candidate-broad-no-edge-multi-horizon-signal-experiment`.
