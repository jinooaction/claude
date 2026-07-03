# Data Model: Learning Ledger Candidate Memory

## LearningLedgerEntry

Existing durable memory entry consumed by the autonomous evolution loop.

| Field | Meaning |
|-------|---------|
| `entry_id` | Stable ledger entry id |
| `candidate_id` | Candidate affected by the decision |
| `decision` | `rejected`, `discard`, `evidence_dependent`, `deferred`, `observe`, or `operator_review` |
| `reason_ko` | Human-readable reason reused in next-action text |
| `evidence_package_id` | Optional source package or sidecar reference |
| `next_recheck_condition` | Optional free-text condition for future human or explicit implementation review |
| `created_at_utc` | Entry creation timestamp |

## SuppressedCandidate

Generated breakthrough candidate after ledger application.

| Field | Meaning |
|-------|---------|
| `candidate_id` | Stable candidate id |
| `status` | Reduced status derived from ledger decision |
| `next_action_ko` | Ledger reason plus recheck/evidence reference when available |
| `recheck_condition` | Preserved condition text |
| `safe_high_leverage_work` membership | Must be false for suppressed decisions |

## CompletedCandidateMarker

Speckit contract marker consumed by released-work after this feature ships.

| Field | Meaning |
|-------|---------|
| `completed_candidate_id` | `candidate-fa66202bf496` |
| `source_path` | Contract document path |
| `status` | `released` after tasks are complete |

## State Transitions

```text
new/generated candidate
  + ledger decision rejected/discard
    -> rejected, not safe_high_leverage_work
  + ledger decision evidence_dependent/deferred/observe
    -> evidence_dependent, not safe_high_leverage_work
  + ledger decision operator_review
    -> operator_review, not safe_high_leverage_work
  + no matching ledger decision
    -> existing generated status
```
