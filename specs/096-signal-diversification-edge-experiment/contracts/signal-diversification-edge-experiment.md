# Contract: Signal Diversification Edge Experiment

completed_candidate_id: candidate-signal-diversification-edge-experiment

## Probe Manifest

`scripts/signal_diversification_edge_experiment_probe.py --manifest` emits:

```text
rebalance-paper-forward	automation/rebalance-paper-forward-last-run	LAST_RUN.md
money-path	automation/money-path-last-run	LAST_RUN.md
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
- `overall_status`
- `headline_ko`
- `required_inputs`
- `evidence_surfaces`
- `signal_families`
- `proposed_signal_candidates`
- `diversification_metrics`
- `money_state`
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

When released-work scans this spec, it must record `candidate-signal-diversification-edge-experiment` as released. Autonomous-work should then advance the investment-edge frontier to `candidate-cost-adjusted-edge-experiment`.
