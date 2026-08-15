# Data Model: Broad No-Edge Tail-Risk Convexity

## ConvexityLane

| Field | Type | Description |
|-------|------|-------------|
| `lane_id` | string | Stable lane id. |
| `status` | enum | `PROPOSED` or `WAIT`. |
| `candidate_rule_ko` | string | Korean no-live rule statement. |
| `required_inputs` | string[] | Sidecar keys needed for this lane. |
| `wait_reason_ko` | string/null | Why the lane cannot be proposed yet. |

## RegimeTailProfile

| Field | Type | Description |
|-------|------|-------------|
| `section_count` | integer | Parsed regime-stratify sections. |
| `total_return_days` | integer | Largest available return day count. |
| `tail_labels` | string[] | Labels with adverse day or drawdown evidence. |
| `worst_day_pct` | number/null | Worst daily return observed across labels. |
| `max_drawdown_pct` | number/null | Largest regime drawdown observed. |

## ExecutionCostProfile

| Field | Type | Description |
|-------|------|-------------|
| `present` | boolean | Whether execution-quality parsed. |
| `overall_status` | string/null | Execution-quality top-level status. |
| `latest_signal` | string/null | Latest opportunity monitor signal. |
| `cumulative_pnl_usd` | number/null | Diagnostic opportunity PnL. |
| `rejected_orders` | integer | Parsed rejected order count. |
| `smoke_state` | string/null | KIS smoke state from the evidence package. |

## ValidationGate

| Field | Type | Description |
|-------|------|-------------|
| `gate_id` | string | Stable gate id. |
| `status` | enum | `PASS`, `WAIT`, or `FAIL`. |
| `summary_ko` | string | Operator-readable reason. |
| `required_evidence` | string[] | Evidence refs. |
