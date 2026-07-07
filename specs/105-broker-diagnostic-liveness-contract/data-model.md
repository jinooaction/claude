# Data Model: Broker Diagnostic Liveness Contract

## BrokerDiagnosticLivenessReport

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Report schema version. |
| `run_id` | string | Workflow or local run id. |
| `commit` | string | Source commit used for the report. |
| `timestamp_utc` | string | Report timestamp. |
| `overall_status` | enum | `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`. |
| `completed_candidate_id` | string | `candidate-broker-diagnostic-liveness-contract`. |
| `next_candidate_id` | string | `candidate-agent-ops-frontier-map`. |
| `evidence_surfaces` | list | Required input presence, parse status, and summary. |
| `kis_smoke_summary` | object | Standalone KIS smoke health and timestamp summary. |
| `execution_quality_summary` | object | Execution-quality status and embedded broker smoke summary. |
| `pipeline_liveness_summary` | object | Pipeline freshness and relevant KIS/execution-quality checks. |
| `diagnostic_summary` | object | Normalized broker diagnostic liveness state. |
| `quality_gates` | list | PASS/WAIT/FAIL gates. |
| `released_work_summary` | object | Whether this candidate is already in released-work. |
| `capital_path_summary` | object | Capital path context proving no live-money mutation. |
| `safety_invariants` | list | Read-only safety boundary. |

## DiagnosticSummary

| Field | Type | Description |
|-------|------|-------------|
| `diagnostic_state` | enum | `BROKER_DIAGNOSTIC_LIVE`, `BROKER_DIAGNOSTIC_OBSERVATION_WAIT`, or `BROKER_DIAGNOSTIC_BLOCKED`. |
| `kis_smoke_success` | boolean | Whether standalone KIS smoke succeeded. |
| `key_valid` | boolean/null | Whether KIS key validity was confirmed. |
| `smoke_exit` | integer/null | Standalone smoke exit code. |
| `tests_total` | integer | Standalone smoke test count. |
| `tests_failed` | integer | Standalone smoke failure count. |
| `execution_quality_has_broker_smoke` | boolean | Whether execution-quality contains broker smoke evidence. |
| `execution_quality_smoke_success` | boolean/null | Whether embedded broker smoke succeeded. |
| `pipeline_overall` | string/null | Pipeline liveness overall status. |
| `pipeline_relevant_checks` | list | Relevant KIS smoke and execution-quality liveness checks. |
| `summary_ko` | string | Operator-readable conclusion. |

## QualityGate

| Field | Type | Description |
|-------|------|-------------|
| `gate_id` | string | Stable gate id. |
| `status` | enum | `PASS`, `WAIT`, or `FAIL`. |
| `summary_ko` | string | Operator-readable status. |
| `evidence_keys` | list | Inputs used by the gate. |

## State Rules

- `BLOCKED`: any quality gate is `FAIL`.
- `OBSERVATION_WAIT`: no gate fails but at least one gate is `WAIT`.
- `CONTRACT_READY`: all gates are `PASS`.

## Completion Marker

```text
completed_candidate_id: candidate-broker-diagnostic-liveness-contract
```
