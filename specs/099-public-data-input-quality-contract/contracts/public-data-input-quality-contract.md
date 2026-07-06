# Contract: Public Data Input Quality

## Completed Work Marker

```yaml
completed_candidate_id: candidate-public-data-input-quality-contract
```

## Consumed Evidence

```yaml
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

## Report Status Contract

- `CONTRACT_READY`: all core evidence parses, public-data publication is complete, cross-checks pass, regime timeline has useful coverage, regime-stratify has at least 20 joined return days, and collect-public-data/regime-stratify liveness is OK.
- `OBSERVATION_WAIT`: core evidence parses but liveness or regime coverage is not yet sufficient.
- `BLOCKED`: required core evidence is missing/malformed, public-data publication is incomplete, or public-data cross-checks fail.

## Minimum JSON Shape

```json
{
  "contract_id": "public-data-input-quality-contract",
  "completed_candidate_id": "candidate-public-data-input-quality-contract",
  "overall_status": "CONTRACT_READY",
  "evidence_surfaces": [
    {
      "key": "public-data-summary",
      "parse_status": "ok",
      "present": true
    }
  ],
  "validation_gates": [
    {
      "gate_id": "publication-completeness",
      "status": "PASS"
    }
  ]
}
```

## Autonomous-Work Advancement Contract

After released-work records `candidate-public-data-input-quality-contract`, autonomous-work MUST select the next unreleased data evidence frontier entry:

```yaml
candidate_id: candidate-regime-timeline-coverage-contract
status: EXECUTION_READY
risk_grade: 2
safety_impact: []
domain_key: data_quality
```

## Safety Contract

The report and probe are read-only. They MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read or write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.
