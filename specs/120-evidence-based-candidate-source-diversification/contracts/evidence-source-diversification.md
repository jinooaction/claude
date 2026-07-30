# Contract: Evidence-Based Candidate Source Diversification

## Inputs

The autonomous work report consumes these existing sidecar surfaces:

- `automation/released-work-last-run:released_work.json`
- `automation/autonomous-evolution-last-run:candidate_backlog.json`
- `automation/autonomous-evolution-last-run:learning_ledger.json`
- `automation/candidate-implementation-factory-last-run:candidate_factory.json`
- `automation/candidate-implementation-factory-last-run:candidate_packages.json`
- `automation/candidate-implementation-results:candidate_results.json`
- `automation/money-path-last-run:LAST_RUN.md`
- `automation/edge-autoarm-last-run:LAST_RUN.md`
- `automation/pipeline-liveness-last-run:LAST_RUN.md`

Inputs may be missing or malformed. Missing noncritical surfaces should degrade the decision rather than create live-money permission.

## Output Requirements

When closed candidates and retryable blocked validation packages are the most actionable remaining evidence, `selected_work` must contain:

```json
{
  "candidate_id": "candidate-evidence-source-diversification-validation-failures",
  "status": "EXECUTION_READY",
  "risk_grade": 2,
  "work_type": "agent_operating_system",
  "reason_ko": "current sidecar evidence summary",
  "next_action_ko": "safe next Codex action",
  "required_inputs": ["sidecar refs"],
  "source_refs": ["sidecar refs"],
  "safety_boundary": ["no broker API call", "no orders", "no capital allocation"],
  "blocked_package_refs": [
    {
      "candidate_id": "candidate id",
      "package_id": "package id",
      "package_kind": "strategy_backtest",
      "retryable": true,
      "diagnostic_codes": ["execution_failed"],
      "next_action_codes": ["inspect_validation_failure"]
    }
  ],
  "validation_failure_groups": [
    {
      "reason_code": "execution_failed",
      "package_count": 2,
      "retryable_count": 2,
      "safe_action_codes": ["inspect_validation_failure"],
      "package_refs": ["pkg id"]
    }
  ]
}
```

The exact output may include additional existing `WorkPacket` fields, but it must preserve the fields above.

## Safety Contract

- The packet is a Codex work item only.
- It must not approve, cancel, or rerun real-money workflows.
- It must not change live arming, capital allocation, position caps, whitelist, drawdown budget, KIS secrets, audit log semantics, or protected environment approvals.
- It must keep sensitive values out of public Markdown and JSON summaries.

## Failure Contract

- If every candidate is closed and no blocked validation package is actionable, the report should return a wait or frontier candidate rather than a released candidate.
- If only unsafe blockers exist, the report should require operator approval or future spec work instead of marking the packet safe to auto-run.
- If money-path is unavailable, the report may still propose read-only candidate diagnostics but must say live-money readiness is unknown.
