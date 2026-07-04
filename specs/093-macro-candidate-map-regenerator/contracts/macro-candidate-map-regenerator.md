# Contract: Macro Candidate Map Regenerator

## Completed Work Marker

```yaml
completed_candidate_id: candidate-macro-candidate-map-regenerator
```

## Next Candidate Contract

When all prior macro/frontier implementation candidates are released, the autonomous-work report MUST emit a map-derived candidate unless a higher-priority regular, operator-approval, blocked, or repair packet exists.

Expected first regenerated candidate:

```yaml
candidate_id: candidate-investment-edge-frontier-map
status: EXECUTION_READY
risk_grade: 2
safety_impact: []
domain_key: strategy_design
```

## Report JSON Additions

The top-level autonomous-work JSON MUST include:

```json
{
  "macro_candidate_map": [
    {
      "domain_key": "investment_edge",
      "coverage_status": "exhausted",
      "recommended_candidate_id": "candidate-investment-edge-frontier-map"
    }
  ]
}
```

Additional map entries are allowed, but they must be deterministic and sorted by descending priority.

## Safety Contract

The generated candidates are work packets only. They MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read or write secrets, modify constitution/kernel files, or invoke paid external services.
