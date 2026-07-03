# Data Model: Autonomous Growth Objective Calibration

## ObjectiveCalibration

Report-level contract emitted by `AutonomousWorkExecutionReport`.

| Field | Type | Notes |
|-------|------|-------|
| `objective_version` | string | Versioned purpose-function contract. Starts at `autonomous-growth-objective-v1`. |
| `selected_candidate_id` | string or null | Mirrors `selected_work.candidate_id` when a candidate exists. |
| `exploration_budget` | object | Work-scope limits for Codex execution. |
| `stop_conditions` | list[string] | Conditions that stop or block autonomous continuation. |
| `learning_metrics` | object | Aggregate queue metrics for repeated improvement. |
| `candidate_scores` | list[ObjectiveCandidateScore] | Top ranked and suppressed candidates scored with the same components. |

## ObjectiveCandidateScore

Deterministic explanation for one `WorkPacket`.

| Field | Type | Notes |
|-------|------|-------|
| `candidate_id` | string | Work candidate identifier. |
| `status` | string | Existing work status such as `EXECUTION_READY` or `OPERATOR_APPROVAL_REQUIRED`. |
| `risk_grade` | integer | Existing risk grade. |
| `priority_score` | integer | Existing queue score, retained for traceability. |
| `component_scores` | object | Five visible component scores, each 0-100. |
| `total_score` | integer | Weighted score used for explanation. |
| `explanation_ko` | string | Short Korean explanation for the score. |

## Component Scores

| Component | Meaning |
|-----------|---------|
| `growth_leverage` | How much the candidate can improve the autonomous growth loop based on priority, domain, and macro status. |
| `evidence_readiness` | Whether required evidence surfaces are present and parseable. |
| `validation_cost_fit` | Whether the expected validation burden fits the loop budget. Lower risk and fewer required inputs score higher. |
| `safety_margin` | Whether the candidate stays away from money path and safety surfaces. Safety impact and high risk lower this score. |
| `learning_value` | Whether completing the candidate teaches the loop how to avoid repeated manual rediscovery. |

## ExplorationBudget

| Field | Type | Contract |
|-------|------|----------|
| `max_ranked_candidates` | integer | 10, matching the report's existing ranked candidate limit. |
| `max_parallel_candidates` | integer | 1, because Codex should finish one candidate through PR and handoff before starting another. |
| `max_validation_minutes` | integer | 90, enough for focused checks, full pytest, lint, harneses, and PR quality gate in this repo. |
| `requires_handoff_refresh` | boolean | True for grade 2 operating automation changes. |
| `requires_pr_quality_gate` | boolean | True for grade 2 operating automation changes. |

## Completed Candidate Contract

The completion field is named `completed_candidate_id`.
The completed candidate value is `candidate-autonomous-growth-objective-calibration`.

This marker is consumed by `released_work` only after all task checkboxes in `tasks.md` are complete.
