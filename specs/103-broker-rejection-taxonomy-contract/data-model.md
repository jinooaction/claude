# Data Model: Broker Rejection Taxonomy Contract

## BrokerRejectionTaxonomyReport

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Report schema version. |
| `run_id` | string | Workflow or local run id. |
| `commit` | string | Source commit used for the report. |
| `timestamp_utc` | string | Report timestamp. |
| `overall_status` | enum | `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`. |
| `completed_candidate_id` | string | `candidate-broker-rejection-taxonomy-contract`. |
| `next_candidate_id` | string | `candidate-execution-cost-basis-contract`. |
| `evidence_surfaces` | list | Required input presence, parse status, and summary. |
| `rejection_summary` | object | Counts and aggregate rejection evidence from execution-quality. |
| `taxonomy` | list | Classified broker rejection signatures. |
| `live_intent_context` | object | Micro GTAA live gate status and no-retry context. |
| `broker_smoke_summary` | object | KIS smoke status from direct smoke sidecar and execution-quality summary. |
| `quality_gates` | list | PASS/WAIT/FAIL gates. |
| `released_work_summary` | object | Whether this candidate is already in released-work. |
| `capital_path_summary` | object | Money path summary proving no live-money mutation. |
| `safety_invariants` | list | Read-only safety boundary. |

## BrokerRejectionClass

| Field | Type | Description |
|-------|------|-------------|
| `signature` | string | Observed broker code or fallback signature. |
| `taxonomy_key` | string | Stable classification key. |
| `label_ko` | string | Operator-readable label. |
| `count` | integer | Number of observations for this signature. |
| `confidence` | enum | `HIGH`, `MEDIUM`, or `LOW`. |
| `recurrence_risk` | enum | `OBSERVED_RECURRENT`, `OBSERVED_SINGLE`, or `UNKNOWN`. |
| `action_category` | enum | `NO_AUTO_RETRY`, `OBSERVE`, or `REPAIR_EVIDENCE`. |
| `reason_ko` | string | Why this classification was chosen. |
| `next_action_ko` | string | Safe next action. |
| `evidence_keys` | list | Input keys supporting the classification. |

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
completed_candidate_id: candidate-broker-rejection-taxonomy-contract
```
