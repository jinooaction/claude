# Contract: Validation Failure Data Readiness

completed_candidate_id: candidate-broad-validation-failure-data-readiness-contract

## JSON Shape

```json
{
  "schema_version": "1.0",
  "overall_status": "CONTRACT_READY",
  "completed_candidate_id": "candidate-broad-validation-failure-data-readiness-contract",
  "package_count": 2,
  "surface_count": 3,
  "data_ready_count": 2,
  "waiting_count": 0,
  "blocked_count": 0,
  "data_readiness_contract": [
    {
      "candidate_id": "candidate-cc96b35062da",
      "package_id": "pkg-8aae8cb99874",
      "readiness_status": "PASS_DATA_READY",
      "data_missing_causes": [],
      "portfolio_paths": [
        "deploy/global-trend-wide-portfolio.toml",
        "deploy/multi-asset-trend-portfolio.toml"
      ],
      "history_roots": [
        "/tmp/candidate_result_history/global-trend-wide/hist",
        "/tmp/candidate_result_history/multi-asset-trend/hist"
      ],
      "observation_window": {
        "start": "2022-06-10",
        "end": "2026-08-10"
      }
    }
  ],
  "safety_invariants": [
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no command execution"
  ]
}
```

## Probe Manifest

```text
candidate-packages	automation/candidate-implementation-factory-last-run	candidate_packages.json
candidate-result-executor	automation/candidate-implementation-results	candidate_results.json
public-data	automation/public-data	LAST_RUN.md
regime-stratify	automation/regime-stratify-last-run	LAST_RUN.md
candidate-history-support	repo	scripts/candidate_history_support_probe.py --json
```
