# Data Model: Agent Harness Regression Liveness Contract

## AgentHarnessRegressionLivenessReport

- `schema_version`: report schema version.
- `run_id`: local or workflow run identifier.
- `commit`: source commit hash associated with the report.
- `timestamp_utc`: report timestamp in UTC.
- `overall_status`: `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`.
- `completed_candidate_id`: always `candidate-agent-harness-regression-liveness-contract`.
- `next_candidate_id`: always `candidate-operator-report-liveness-contract`.
- `evidence_surfaces`: tuple of `EvidenceSurface`.
- `harness_suite_summary`: normalized suite evaluator result.
- `strict_observation_summary`: normalized supplied strict output result.
- `quality_gates`: tuple of `QualityGate`.
- `released_work_summary`: normalized released-work result.
- `safety_invariants`: read-only safety boundary statements.

## EvidenceSurface

- `key`: stable evidence key.
- `source_ref`: file path, sidecar reference, or supplied evidence label.
- `present`: whether evidence text or local file exists.
- `parse_status`: `ok`, `present`, `missing`, or `malformed`.
- `summary_ko`: short Korean summary.

## QualityGate

- `gate_id`: stable gate identifier.
- `status`: `PASS`, `WAIT`, or `FAIL`.
- `summary_ko`: Korean explanation of the decision.
- `evidence_keys`: evidence keys used by the gate.

## HarnessSuiteSummary

- `task_suite`: status, task count, risk grades, control categories, messages.
- `quality_suite`: status, task count, required categories, messages.
- `redteam_suite`: status, task count, attack types, messages.

## StrictObservationSummary

- `state`: `PASS`, `WAIT`, or `FAIL`.
- `parse_status`: `ok`, `missing`, or `malformed`.
- `status`: parsed harness status when known.
- `score`: parsed passed control count when known.
- `max_score`: parsed total control count when known.
- `summary_ko`: Korean explanation.

## ReleasedWorkSummary

- `parse_status`: `ok`, `missing`, or `malformed`.
- `completed_candidate_id`: `candidate-agent-harness-regression-liveness-contract`.
- `completed_candidate_released`: boolean.
- `released_count`: number of released candidates seen.

## State Rules

- Any `FAIL` gate makes `overall_status=BLOCKED`.
- If no gate fails but at least one gate is `WAIT`, `overall_status=OBSERVATION_WAIT`.
- If all gates pass, `overall_status=CONTRACT_READY`.
