# Contract: Frontier Candidate Discovery

completed_candidate_id: candidate-autonomous-frontier-discovery

## JSON Contract

When known queues are exhausted, `AutonomousWorkExecutionReport.to_dict()` MUST include:

```json
{
  "overall_status": "EXECUTION_READY",
  "selected_work": {
    "candidate_id": "candidate-autonomous-frontier-discovery",
    "status": "EXECUTION_READY",
    "risk_grade": 2,
    "safety_impact": [],
    "autonomy_level": "CODEX_AUTONOMOUS_START"
  }
}
```

The candidate reason MUST include closed, released, and suppressed candidate counts. The candidate source references MUST include released-work, pipeline-liveness, capital-path-readiness, and autonomous-work evidence surfaces available to the loop.

## Safety Contract

This feature MUST NOT call a broker, place orders, allocate capital, change live strategy, change whitelist/caps, read or write secrets, change constitution/kernel files, or call a paid external service.
