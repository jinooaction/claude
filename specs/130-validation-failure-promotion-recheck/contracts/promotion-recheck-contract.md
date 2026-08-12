# Contract: Validation Failure Promotion Recheck

completed_candidate_id: candidate-broad-validation-failure-promotion-recheck-contract

## JSON Shape

```json
{
  "schema_version": "1.0",
  "overall_status": "CONTRACT_READY",
  "completed_candidate_id": "candidate-broad-validation-failure-promotion-recheck-contract",
  "candidate_count": 2,
  "suppressed_count": 2,
  "allowed_recheck_count": 0,
  "candidate_rules": [
    {
      "candidate_id": "candidate-1ed634d8bf6d",
      "decision_status": "SUPPRESSION_ACTIVE",
      "ledger_decision": "rejected",
      "promotion_stage": "DISCARD",
      "result_status": "fail",
      "promotion_package_id": "pkg-c9a284fa4235",
      "promotion_package_kind": "strategy_backtest",
      "failure_fingerprint": "<stable digest>",
      "recheck_conditions": [
        {
          "condition_key": "candidate_result_not_failed",
          "is_currently_met": false
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
    "no external paid service",
    "no command execution"
  ]
}
```

## Probe Manifest

```text
learning-ledger	automation/autonomous-evolution-last-run	learning_ledger.json
autonomous-promotion	automation/autonomous-promotion-last-run	promotion_summary.json
candidate-result-executor	automation/candidate-implementation-results	candidate_results.json
```
