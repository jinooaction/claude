# Contract: Forward Regime Edge Experiment

## Completed Work Marker

```yaml
completed_candidate_id: candidate-forward-regime-edge-experiment
```

## Required Inputs

```yaml
required_inputs:
  - automation/rebalance-paper-forward-last-run:LAST_RUN.md
  - automation/money-path-last-run:LAST_RUN.md
  - automation/released-work-last-run:released_work.json
  - automation/autonomous-evolution-last-run:learning_ledger.json
  - automation/pipeline-liveness-last-run:LAST_RUN.md
```

## Report JSON Contract

The probe MUST emit a JSON object containing at least:

```json
{
  "schema_version": "1.0",
  "experiment_id": "forward-regime-edge-experiment",
  "completed_candidate_id": "candidate-forward-regime-edge-experiment",
  "overall_status": "OBSERVATION_WAIT",
  "evidence_surfaces": [],
  "forward_tracks": [],
  "money_state": {},
  "validation_gates": [],
  "safety_boundary": []
}
```

## Validation Gates

The report MUST include these gates:

- `input-evidence`: all five required sidecars are present and parseable enough for the contract.
- `pipeline-liveness`: critical sidecars are alive.
- `no-live-safety`: report remains read-only and does not enable real orders.
- `forward-comparability`: incumbent and candidate tracks have enough observations for fair comparison.
- `regime-brittleness`: regime context is surfaced so brittle performance is not hidden.
- `released-work-closure`: this spec marks only `candidate-forward-regime-edge-experiment` complete.

## Safety Contract

The generated report is an experiment contract only. It MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read or write secrets, modify constitution/kernel files, or invoke paid external services.
