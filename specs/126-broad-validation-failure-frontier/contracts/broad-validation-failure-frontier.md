# Contract: Broad Validation Failure Frontier

completed_candidate_id: candidate-broad-frontier-expansion-validation-failures-22f38b8629eb

## JSON Additions

`build_autonomous_work_execution(...).to_dict()` MUST include:

```json
{
  "broad_validation_failure_frontier_map": [
    {
      "frontier_key": "command_replay_contract",
      "coverage_status": "open",
      "recommended_candidate_id": "candidate-broad-validation-failure-command-replay-contract",
      "package_count": 2,
      "retryable_count": 2,
      "failure_codes": ["execution_failed"],
      "package_kinds": ["strategy_backtest", "portfolio_backtest"],
      "review_axes": ["validation_command", "exit_code", "safe_replay", "output_digest"]
    }
  ]
}
```

## Work Packet Selection

When all are true:

- released-work contains `candidate-broad-frontier-expansion-validation-failures-<fingerprint>`;
- retryable blocked validation packages remain;
- no higher-priority execution-ready, operator-approval, or blocked packet exists;

then selected work MUST be the first open validation-failure frontier entry, initially `candidate-broad-validation-failure-command-replay-contract`.

## Safety Boundary

Every emitted child packet MUST include:

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no secret read/write
- no external paid service
- validation-failure fingerprint analysis only
