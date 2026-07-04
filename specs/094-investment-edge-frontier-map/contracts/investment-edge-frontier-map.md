# Contract: Investment Edge Frontier Map

## Completed Work Marker

```yaml
completed_candidate_id: candidate-investment-edge-frontier-map
```

## Next Candidate Contract

When `candidate-investment-edge-frontier-map` is released, the autonomous-work report MUST emit the first unreleased no-live investment-edge experiment candidate unless a higher-priority regular, operator-approval, blocked, or repair packet exists.

Expected first no-live candidate:

```yaml
candidate_id: candidate-forward-regime-edge-experiment
status: EXECUTION_READY
risk_grade: 2
safety_impact: []
domain_key: strategy_design
required_inputs:
  - automation/rebalance-paper-forward-last-run:LAST_RUN.md
  - automation/money-path-last-run:LAST_RUN.md
  - automation/released-work-last-run:released_work.json
  - automation/autonomous-evolution-last-run:learning_ledger.json
  - automation/pipeline-liveness-last-run:LAST_RUN.md
```

## Report JSON Additions

The top-level autonomous-work JSON MUST include:

```json
{
  "investment_edge_frontier_map": [
    {
      "frontier_key": "forward_regime_edge",
      "coverage_status": "open",
      "recommended_candidate_id": "candidate-forward-regime-edge-experiment"
    }
  ]
}
```

Additional investment-edge entries are allowed, but they must be deterministic and sorted by descending priority.

## Safety Contract

The generated candidates are work packets only. They MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read or write secrets, modify constitution/kernel files, or invoke paid external services.
