# Data Model: Broad No-Edge Vol-Target Drawdown

## DrawdownLane

| Field | Type | Description |
|-------|------|-------------|
| `lane_id` | string | Stable lane id. |
| `status` | enum | `PROPOSED` or `WAIT`. |
| `candidate_rule_ko` | string | Korean no-live rule statement. |
| `required_inputs` | string[] | Sidecar keys needed for this lane. |
| `wait_reason_ko` | string/null | Why the lane cannot be proposed yet. |

## ForwardTrack

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Stable forward track key. |
| `verdict` | string/null | Forward verdict such as `NO_EDGE`. |
| `n_obs` | integer/null | Forward observation count. |
| `psr_vs_benchmark` | number/null | Probability-style edge confidence against benchmark. |
| `calmar` | number/null | Return per drawdown metric. |
| `max_drawdown_pct` | number/null | Track maximum drawdown percentage. |

## MoneyState

| Field | Type | Description |
|-------|------|-------------|
| `status` | string/null | Live money status from money-path. |
| `can_submit_real_orders` | boolean/null | Whether real orders are currently submit-capable. |
| `stage` | string/null | Capital ladder stage. |
| `current_rung` | integer/null | Current capital ladder rung. |
| `demote_dd_pct` | number/null | Prospective demotion drawdown budget. |
| `halt_dd_pct` | number/null | Prospective absolute halt drawdown budget. |

## EdgeAutoarmState

| Field | Type | Description |
|-------|------|-------------|
| `action` | string/null | Edge-autoarm action such as `WAIT_EDGE`. |
| `reason` | string/null | Operator-readable reason. |
| `current_rung` | integer/null | Rung observed by edge-autoarm. |
| `live_dd_pct` | number/null | Live drawdown percentage evidence. |
| `forward_verdict` | string/null | Forward verdict consumed by edge-autoarm. |

## ValidationGate

| Field | Type | Description |
|-------|------|-------------|
| `gate_id` | string | Stable gate id. |
| `status` | enum | `PASS`, `WAIT`, or `FAIL`. |
| `summary_ko` | string | Operator-readable reason. |
| `required_evidence` | string[] | Evidence refs. |
