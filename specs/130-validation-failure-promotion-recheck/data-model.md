# Data Model: Validation Failure Promotion Recheck Contract

## Promotion Recheck Contract

- `schema_version`: contract schema version.
- `run_id`, `commit`, `timestamp_utc`: provenance only, not fingerprint inputs.
- `overall_status`: `CONTRACT_READY` or `WAITING_FOR_EVIDENCE`.
- `completed_candidate_id`: `candidate-broad-validation-failure-promotion-recheck-contract`.
- `candidate_count`, `suppressed_count`, `allowed_recheck_count`, `waiting_count`: aggregate counts.
- `candidate_rules`: deterministic candidate-level rules.
- `missing_inputs`: structurally missing sidecars.
- `safety_invariants`: no-live safety boundary.

## Candidate Recheck Rule

- `candidate_id`
- `decision_status`: `SUPPRESSION_ACTIVE`, `RECHECK_ALLOWED`, or `WAITING_FOR_EVIDENCE`.
- `ledger_decision`, `ledger_entry_id`, `ledger_evidence_package_id`
- `ledger_recheck_condition`, `historical_recheck_conditions`
- `promotion_stage`, `promotion_source_status`, `promotion_package_id`, `promotion_package_kind`, `promotion_retryable`
- `result_status`, `validation_layers`, `metric_highlights`
- `failure_fingerprint`
- `recheck_conditions`
- `next_action_code`, `next_action_ko`
- `source_refs`

## Recheck Condition

- `condition_key`: stable machine key.
- `label_ko`: operator-readable label.
- `description_ko`: exact future evidence change required.
- `is_currently_met`: whether current evidence already satisfies the condition.

## State Transitions

- Latest ledger rejected + promotion discard + result fail or blocked -> `SUPPRESSION_ACTIVE`.
- Result no longer fail/blocked -> `RECHECK_ALLOWED`.
- Promotion no longer discard/rejected -> `RECHECK_ALLOWED`.
- Latest ledger explicit recheck condition -> `RECHECK_ALLOWED`.
- Missing ledger, promotion, or result for a target candidate -> `WAITING_FOR_EVIDENCE`.
- `completed_candidate_id: candidate-broad-validation-failure-promotion-recheck-contract` -> released-work can close the final validation-failure child.
