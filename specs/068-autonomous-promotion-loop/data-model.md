# Data Model: Autonomous Promotion Loop

## PromotionCandidate

- `candidate_id`: Stable source candidate id.
- `title_ko`: Operator-facing title.
- `domain_key`: Source domain.
- `source_status`: Source lifecycle state from autonomous evolution.
- `risk_grade`: Existing risk grade.
- `safety_impact`: Safety surfaces detected by the source loop.
- `evidence_refs`: Source evidence keys.
- `next_action_ko`: Source next action.

## EvidenceLayer

- `name`: `historical_backtest`, `recent_oos`, `walk_forward`, `forward_paper`, `small_live_canary`, `existing_gate`.
- `status`: `missing`, `pending`, `pass`, `fail`, or `unknown`.
- `detail_ko`: Human-readable reason.
- `source_ref`: Sidecar or artifact reference.

## PromotionAssessment

- `candidate_id`
- `stage`: Current promotion stage.
- `allowed_next_action`: Safe next action.
- `blocked_reason_ko`: Why the candidate cannot advance further.
- `strategy_validation_complete`: Whether strategy logic evidence is sufficient.
- `execution_validation_complete`: Whether live broker execution path evidence exists.
- `next_gate`: Existing gate if applicable.
- `evidence_layers`: Ordered evidence layer statuses.

## PromotionRunSummary

- `schema_version`
- `run_id`
- `commit`
- `timestamp_utc`
- `overall_status`
- `assessments`
- `operator_review`
- `missing_evidence`
