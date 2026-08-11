# Contract: Validation Failure Command Replay

## Completed Candidate

completed_candidate_id: candidate-broad-validation-failure-command-replay-contract

## Input Sidecars

- `automation/candidate-implementation-factory-last-run:candidate_packages.json`
- `automation/candidate-implementation-results:candidate_results.json`

## JSON Shape

```json
{
  "schema_version": "1.0",
  "overall_status": "CONTRACT_READY",
  "completed_candidate_id": "candidate-broad-validation-failure-command-replay-contract",
  "package_count": 2,
  "command_count": 4,
  "replay_safe_count": 4,
  "missing_execution_count": 4,
  "unsafe_command_count": 0,
  "command_replay_contract": [
    {
      "candidate_id": "candidate-1ed634d8bf6d",
      "package_id": "pkg-c9a284fa4235",
      "package_kind": "strategy_backtest",
      "command_index": 1,
      "command_digest": "stable-hex",
      "safe_to_replay": true,
      "replay_scope": "allowlisted_no_live_validation",
      "observed_exit_code": null,
      "exit_code_evidence_status": "missing_execution_evidence",
      "diagnostic_codes": ["execution_failed"],
      "next_action_code": "inspect_validation_failure"
    }
  ],
  "safety_invariants": [
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no command execution"
  ]
}
```

## Markdown Shape

Markdown output MUST include:

- A title `검증 실패 명령 재현 계약`.
- A summary table with overall status and counts.
- A `명령별 계약` table.
- A `안전 경계` section.

## Safety Contract

The probe MUST NOT execute candidate package commands. It only classifies and summarizes evidence. Any live, broker, capital, secret, whitelist/caps, sentinel, SSH, or unsupported command surface must be marked unsafe.
