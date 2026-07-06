# Contract: Regime Timeline Coverage

## Completed Work Marker

```yaml
completed_candidate_id: candidate-regime-timeline-coverage-contract
```

## Consumed Evidence

```yaml
required_inputs:
  - automation/public-data:regime_timeline.csv
  - automation/regime-stratify-last-run:LAST_RUN.md
  - automation/pipeline-liveness-last-run:LAST_RUN.md
  - automation/released-work-last-run:released_work.json
```

## Report Status Contract

- `CONTRACT_READY`: timeline parses with date/label shape, canonical labels exist, every stratified section has an explicit forward d+1 join rule, label count sums match total return days, every canonical label has at least 20 joined return days, and collect-public-data/regime-stratify liveness is OK.
- `OBSERVATION_WAIT`: core evidence parses and the forward join is structurally valid, but liveness is stale/waiting or one or more canonical labels have fewer than 20 joined return days.
- `BLOCKED`: required core evidence is missing/malformed, timeline shape is invalid, stratified JSON is missing, join rule is not forward-looking, or label counts do not match total return days.

## Minimum JSON Shape

```json
{
  "schema_version": "1.0",
  "completed_candidate_id": "candidate-regime-timeline-coverage-contract",
  "next_candidate_id": "candidate-data-evidence-liveness-contract",
  "overall_status": "OBSERVATION_WAIT",
  "evidence_surfaces": [
    {
      "key": "public-data-regime-timeline",
      "parse_status": "ok",
      "present": true
    }
  ],
  "quality_gates": [
    {
      "key": "stratified_observation_floor",
      "status": "WAIT"
    }
  ],
  "stratified_summary": {
    "section_count": 2,
    "sparse_labels": ["GLOBAL-TREND:RISK_OFF"]
  }
}
```

## Autonomous-Work Advancement Contract

After released-work records `candidate-regime-timeline-coverage-contract`, autonomous-work MUST select the next unreleased data evidence frontier entry:

```yaml
candidate_id: candidate-data-evidence-liveness-contract
status: EXECUTION_READY
risk_grade: 2
safety_impact: []
domain_key: data_quality
```

## Safety Contract

The report and probe are read-only. They MUST NOT call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read or write secrets, modify constitution/kernel files, run fresh external collection, or invoke paid external services.
