# Contract: Autonomous Growth Objective Calibration

completed_candidate_id: candidate-autonomous-growth-objective-calibration

## JSON Contract

`AutonomousWorkExecutionReport.to_dict()` MUST include:

```json
{
  "objective_calibration": {
    "objective_version": "autonomous-growth-objective-v1",
    "selected_candidate_id": "candidate-autonomous-growth-objective-calibration",
    "exploration_budget": {
      "max_ranked_candidates": 10,
      "max_parallel_candidates": 1,
      "max_validation_minutes": 90,
      "requires_handoff_refresh": true,
      "requires_pr_quality_gate": true
    },
    "stop_conditions": [
      "operator approval required for safety-impact or grade >=4 work",
      "no autonomous merge when full pytest or ruff fails",
      "no autonomous merge when strict agent harness fails",
      "no autonomous start when required sidecar evidence is missing or malformed"
    ],
    "learning_metrics": {
      "ranked_count": 1,
      "suppressed_count": 10,
      "operator_approval_count": 0,
      "released_count": 8,
      "safety_impact_count": 0
    },
    "candidate_scores": [
      {
        "candidate_id": "candidate-autonomous-growth-objective-calibration",
        "status": "EXECUTION_READY",
        "risk_grade": 2,
        "priority_score": 2600,
        "component_scores": {
          "growth_leverage": 86,
          "evidence_readiness": 100,
          "validation_cost_fit": 75,
          "safety_margin": 100,
          "learning_value": 95
        },
        "total_score": 91,
        "explanation_ko": "안전 경계 안에서 자율 성장 루프의 반복 판단 비용을 줄이는 후보입니다."
      }
    ]
  }
}
```

Exact component values may differ as long as they are deterministic, 0-100 bounded, and satisfy the safety and evidence contracts.

## Markdown Contract

`AutonomousWorkExecutionReport.as_markdown()` MUST include a `## 목적 함수 보정` section with:

- Selected candidate id
- Exploration budget values
- Stop conditions
- A candidate score table

## Safety Contract

This feature MUST NOT call a broker, place orders, allocate capital, change live strategy, change whitelist/caps, read or write secrets, change constitution/kernel files, or call a paid external service.
