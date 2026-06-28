# Data Model: Autonomous Evolution Loop

## EvolutionDomain

- `key`: Stable domain identifier such as `data_collection`, `data_quality`, `analysis`, `strategy_design`, `portfolio_design`, `execution_quality`, `live_readiness`, `review`, `agent_ops`.
- `label_ko`: Korean display label.
- `description`: What the domain covers.
- `default_priority`: Baseline ordering when evidence is otherwise equal.
- `safety_notes`: Domain-specific safety constraints.

## EvidenceSurface

- `key`: Stable source identifier.
- `kind`: `sidecar`, `handoff`, `spec`, `test`, `workflow`, `local_probe`, or `manual_note`.
- `source_ref`: Branch/file, local path, command, or commit reference.
- `observed_at_utc`: Timestamp of the evidence itself if available.
- `producer_commit`: Commit that produced the evidence if available.
- `freshness_status`: `fresh`, `late`, `stale`, `missing`, or `unknown`.
- `summary_ko`: Korean summary with secrets masked.
- `machine_payload`: Optional parsed JSON payload.

## BreakthroughCandidate

- `candidate_id`: Stable content-derived identifier.
- `domain_key`: Related `EvolutionDomain`.
- `title_ko`: Korean short title.
- `problem_ko`: Problem statement.
- `evidence_refs`: EvidenceSurface keys.
- `expected_benefit`: `profit`, `risk_reduction`, `speed`, `reliability`, `observability`, `cost`, or `operator_time`.
- `breakthrough_type`: `profit_power`, `evidence_quality`, `capital_path`, `safety`, `learning_velocity`, `execution_quality`, or `operator_leverage`.
- `growth_leverage`: Deterministic score for expected long-term profit-capacity impact.
- `capability_compounding`: Deterministic score for whether the work makes future improvement loops faster or stronger.
- `capital_path_alignment`: Deterministic score for whether the work safely moves validated edge closer to existing capital gates.
- `evidence_dependency`: `none`, `market_observation`, `sidecar_freshness`, `external_data`, `operator_review`, or `new_experiment`.
- `confidence`: `low`, `medium`, `high`.
- `risk_grade`: 0-4 according to `AGENTS.md`.
- `safety_impact`: List of touched surfaces such as `orders`, `capital`, `whitelist`, `caps`, `secrets`, `deploy`, `kernel`, `paid_service`.
- `status`: `new`, `planned`, `running`, `evidence_dependent`, `promoted`, `rejected`, `expired`, or `operator_review`.
- `next_action_ko`: The next safe action.
- `expires_at_utc`: Optional time after which the candidate must be rescanned.
- `recheck_condition`: Evidence condition needed before the candidate can return.

## ExperimentPlan

- `experiment_id`: Stable identifier.
- `candidate_id`: Parent candidate.
- `goal_ko`: What the experiment proves or disproves.
- `non_goals_ko`: Explicit exclusions.
- `required_data`: Evidence and datasets needed.
- `success_metrics`: Metrics and thresholds.
- `failure_criteria`: Conditions that discard or pause the candidate.
- `allowed_stage`: `read_only`, `backtest`, `paper`, `canary`, or `operator_review`.
- `affected_paths`: Expected repository paths if implementation follows.
- `rollback_or_discard_ko`: How to undo or reject the work.

## EvidencePackage

- `package_id`: Stable identifier.
- `experiment_id`: Parent experiment.
- `result`: `pass`, `fail`, `inconclusive`, or `blocked`.
- `baseline`: Comparison baseline.
- `measurements`: Metric name/value pairs.
- `limitations_ko`: Known limits.
- `safety_review_ko`: Safety boundary review.
- `recommended_decision`: `discard`, `observe`, `create_spec`, `open_pr`, `feed_existing_gate`, or `operator_review`.

## LearningLedgerEntry

- `entry_id`: Stable identifier.
- `candidate_id`: Related candidate.
- `decision`: `accepted`, `rejected`, `evidence_dependent`, `expired`, or `superseded`.
- `reason_ko`: Why the decision was made.
- `evidence_package_id`: Optional evidence package.
- `next_recheck_condition`: What new evidence can reopen it.
- `created_at_utc`: Entry timestamp.

## EvolutionRunSummary

- `schema_version`: Report schema.
- `run_id`: Automation or local run identifier.
- `commit`: Code commit used by the scan.
- `timestamp_utc`: Run timestamp.
- `overall_status`: `ok`, `degraded`, or `blocked`.
- `top_breakthrough_candidates`: Ordered candidate IDs.
- `safe_high_leverage_work`: Candidate IDs that can proceed inside existing safety gates.
- `evidence_dependencies`: Candidate IDs grouped by dependency type, including market observation when relevant.
- `operator_review`: Candidate IDs requiring explicit operator decision.
- `stale_evidence`: EvidenceSurface keys that are stale or missing.
