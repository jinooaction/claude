# Contract: Source Diversification Candidate Closure

## Released Work Marker

```yaml
completed_candidate_id: candidate-source-diversification-sidecar-bottleneck
feature: 090-source-diversification-candidate-closure
risk_grade: 2
safety_boundary:
  - no broker API call
  - no orders
  - no capital allocation
  - no live strategy change
  - no whitelist/caps change
  - no secret read/write
  - no external paid service
```

## Autonomous Work Replay Contract

After released-work consumes this marker and the latest sidecars are replayed with repository completion evidence, the selected work should advance to:

```yaml
next_macro_candidate: candidate-autonomous-growth-objective-calibration
expected_status: EXECUTION_READY
expected_risk_grade: 2
expected_safety_impact: []
```

## Non-Goals

- No order submission or broker API call.
- No live strategy, capital ladder, whitelist/caps, secret, constitution, or kernel change.
- No new paid data or external service.
- No ranking rewrite unless regression evidence proves the existing released-work path is insufficient.
