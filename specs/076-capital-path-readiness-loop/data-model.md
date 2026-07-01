# Data Model: Capital Path Readiness Loop

## ReadinessEvidenceSurface

| Field | Type | Validation |
|-------|------|------------|
| `key` | string | Stable evidence key |
| `source_ref` | string | `branch:filename` or local source |
| `present` | boolean | False when sidecar missing |
| `parse_status` | string | `ok`, `missing`, `malformed`, or `not_required` |
| `summary_ko` | string | Short human explanation |

## CapitalPathReadinessReport

| Field | Type | Validation |
|-------|------|------------|
| `schema_version` | string | `1.0` |
| `run_id` | string | Workflow run id or local |
| `commit` | string | Source commit |
| `timestamp_utc` | string | ISO-8601 UTC |
| `readiness_state` | string | `ACCUMULATING_EDGE`, `EDGE_READY`, `CAPITAL_ARMABLE`, `PREVIEW_ONLY`, `LIVE_BLOCKED`, `OPERATOR_ONLY`, or `UNKNOWN` |
| `live_money_status` | string | From money-path `live_money_state.status` or `UNKNOWN` |
| `capital_ladder_stage` | string | From money-path `stage` or `UNKNOWN` |
| `blocking_gate` | string | Non-empty explanation |
| `next_action_ko` | string | Non-empty next safe action |
| `required_existing_gates` | list[string] | Existing gates only |
| `priority_candidates` | list[ReadinessCandidate] | Non-rejected candidates relevant to capital path |
| `suppressed_candidates` | list[ReadinessCandidate] | Rejected candidates excluded from active readiness |
| `evidence_surfaces` | list[ReadinessEvidenceSurface] | All consumed inputs |

## ReadinessCandidate

| Field | Type | Validation |
|-------|------|------------|
| `candidate_id` | string | Stable candidate id |
| `domain_key` | string | Candidate domain |
| `status` | string | Candidate status or ledger decision |
| `title_ko` | string | Human-readable title |
| `reason_ko` | string | Why priority or suppressed |
| `source` | string | `candidate_backlog`, `learning_ledger`, or `promotion_summary` |

## State Transitions

```text
UNKNOWN -> ACCUMULATING_EDGE -> EDGE_READY -> CAPITAL_ARMABLE
UNKNOWN -> PREVIEW_ONLY
UNKNOWN -> LIVE_BLOCKED
any state -> OPERATOR_ONLY when the next required action is operator-only
```

The loop never transitions a live strategy, capital rung, order, whitelist, or cap. It only reports readiness.
