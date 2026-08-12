# Contract: Validation Failure Package-Kind Expansion

completed_candidate_id: candidate-broad-validation-failure-package-kind-expansion-contract

## JSON Shape

```json
{
  "schema_version": "1.0",
  "overall_status": "CONTRACT_READY",
  "completed_candidate_id": "candidate-broad-validation-failure-package-kind-expansion-contract",
  "package_count": 2,
  "bucket_count": 2,
  "retryable_count": 2,
  "package_kind_expansion_contract": [
    {
      "package_kind": "portfolio_backtest",
      "bucket_status": "READY_FOR_AXIS_EXPANSION",
      "failure_codes": ["execution_failed"],
      "review_axes": ["portfolio_design", "asset_universe", "holding_period", "benchmark_comparison"],
      "experiment_axes": [
        {
          "axis_key": "portfolio_design",
          "label_ko": "포트폴리오 구성 재검토"
        }
      ],
      "package_refs": [
        {
          "candidate_id": "candidate-cc96b35062da",
          "package_id": "pkg-8aae8cb99874",
          "result_status": "fail"
        }
      ]
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
```
