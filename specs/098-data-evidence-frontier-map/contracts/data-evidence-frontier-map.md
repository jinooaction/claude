# Contract: Data Evidence Frontier Map

## Completed Work Marker

```yaml
completed_candidate_id: candidate-data-evidence-frontier-map
```

## Next Candidate Contract

When `candidate-data-evidence-frontier-map` is released, the autonomous-work report MUST emit the first unreleased data evidence input-quality candidate unless a higher-priority regular, operator-approval, blocked, or repair packet exists.

Expected first input-quality candidate:

```yaml
candidate_id: candidate-public-data-input-quality-contract
status: EXECUTION_READY
risk_grade: 2
safety_impact: []
domain_key: data_quality
required_inputs:
  - automation/public-data:LAST_RUN.md
  - automation/public-data:summary.json
  - automation/public-data:regime.json
  - automation/public-data:regime_timeline.csv
  - automation/regime-stratify-last-run:LAST_RUN.md
  - automation/pipeline-liveness-last-run:LAST_RUN.md
  - automation/released-work-last-run:released_work.json
  - automation/capital-path-readiness-last-run:capital_path_readiness.json
```

## Report JSON Additions

The top-level autonomous-work JSON MUST include:

```json
{
  "data_evidence_frontier_map": [
    {
      "frontier_key": "public_data_input_quality",
      "coverage_status": "open",
      "recommended_candidate_id": "candidate-public-data-input-quality-contract"
    }
  ]
}
```

Additional data-evidence entries are allowed, but they must be deterministic and sorted by descending priority.

## Safety Contract

The generated candidates are work packets only. They MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read or write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.
