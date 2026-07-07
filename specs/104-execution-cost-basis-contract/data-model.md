# Data Model: Execution Cost Basis Contract

## ExecutionCostBasisReport

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Report schema version. |
| `run_id` | string | Workflow or local run id. |
| `commit` | string | Source commit used for the report. |
| `timestamp_utc` | string | Report timestamp. |
| `overall_status` | enum | `CONTRACT_READY`, `OBSERVATION_WAIT`, or `BLOCKED`. |
| `completed_candidate_id` | string | `candidate-execution-cost-basis-contract`. |
| `next_candidate_id` | string | `candidate-broker-diagnostic-liveness-contract`. |
| `evidence_surfaces` | list | Required input presence, parse status, and summary. |
| `execution_quality_summary` | object | Overall execution-quality parse state and whether a cost-basis block exists. |
| `money_path_summary` | object | Live-money status and accepted/fill counts from money-path evidence. |
| `cost_basis_summary` | object | Normalized accepted/fill cost basis state. |
| `quality_gates` | list | PASS/WAIT/FAIL gates. |
| `released_work_summary` | object | Whether this candidate is already in released-work. |
| `capital_path_summary` | object | Capital path summary proving no live-money mutation. |
| `safety_invariants` | list | Read-only safety boundary. |

## CostBasisSummary

| Field | Type | Description |
|-------|------|-------------|
| `cost_basis_state` | enum | `COST_BASIS_READY`, `COST_BASIS_OBSERVATION_WAIT`, or `COST_BASIS_BLOCKED`. |
| `execution_quality_has_cost_basis` | boolean | Whether `execution_quality.execution_cost_basis` exists. |
| `basis_complete` | boolean | Whether measurable accepted/fill basis is sufficient for ready status. |
| `accepted_or_filled_orders` | integer | Accepted/fill count from execution-quality or money-path. |
| `measurable_fills` | integer | Number of fills with measurable cost basis. |
| `unmeasurable_fills` | integer | Number of accepted/fill observations lacking cost basis. |
| `turnover_observed` | boolean | Whether turnover evidence is present. |
| `avg_slippage_bps` | number/null | Average slippage in basis points when available. |
| `median_slippage_bps` | number/null | Median slippage in basis points when available. |
| `total_cost_usd` | number/null | Total observed cost when available. |
| `live_money_status` | string/null | Money-path live-money status. |
| `can_submit_real_orders` | boolean/null | Whether money-path can submit real orders. |
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
completed_candidate_id: candidate-execution-cost-basis-contract
```
