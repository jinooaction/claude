# Data Model: Strategy Failure Learning

## Promotion Failure Signal

Derived from `promotion_summary.json`.

| Field | Type | Rule |
|-------|------|------|
| `candidate_id` | string | Required, non-empty. |
| `title_ko` | string | Optional display title from assessment candidate. |
| `stage` | string | Must equal `DISCARD` to become a failure signal. |
| `reason_ko` | string | Prefer `blocked_reason_ko`; fall back to allowed next action or default failure text. |
| `evidence_package_id` | string | `autonomous-promotion:<run_id>` when run id exists. |

## Learning Ledger Entry

Existing entity from spec 067.

| Field | Type | Rule |
|-------|------|------|
| `entry_id` | string | Stable id from candidate id and decision. |
| `candidate_id` | string | Same candidate id as the failure signal. |
| `decision` | string | `rejected` for `DISCARD` promotion signals. |
| `reason_ko` | string | Failure reason from promotion signal. |
| `evidence_package_id` | string or null | Source reference for the promotion run. |
| `next_recheck_condition` | string or null | Null for current factory/promotion failure unless future input explicitly supplies a recheck condition. |
| `created_at_utc` | string | Current evolution scan timestamp. |

## State Transitions

```text
promotion_summary assessment stage DISCARD
  -> Promotion Failure Signal
  -> Learning Ledger Entry(decision=rejected)
  -> future scan apply_learning_ledger
  -> BreakthroughCandidate(status=rejected)
```

Existing `rejected` entries are not duplicated. Existing entries with a non-empty recheck condition are preserved.
