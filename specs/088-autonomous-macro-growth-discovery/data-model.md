# Data Model: Autonomous Macro Growth Discovery

## Regular Work Packet

Existing work packet produced from normal sidecar inputs before macro synthesis.

| Field | Meaning |
|-------|---------|
| `candidate_id` | Stable candidate identifier |
| `status` | `EXECUTION_READY`, `OPERATOR_APPROVAL_REQUIRED`, `BLOCKED`, `RELEASED`, or `SUPPRESSED` |
| `source_refs` | Evidence sidecars that produced the packet |
| `priority_score` | Existing deterministic ordering score |

## Closed Queue Signal

Derived signal, not persisted separately.

| Rule | Meaning |
|------|---------|
| No regular packet is `EXECUTION_READY` | There is no ordinary autonomous task to start |
| No regular packet is `OPERATOR_APPROVAL_REQUIRED` or `BLOCKED` | Safety or recovery work is not being hidden |
| Remaining regular packets are `RELEASED` or `SUPPRESSED` | Queue is closed, not merely uncertain |
| Evidence is not globally missing | Missing evidence remains a repair task |

## Macro Growth Candidate

Deterministic work packet emitted from the closed queue signal.

| Candidate | Purpose |
|-----------|---------|
| `candidate-macro-growth-discovery` | Bootstrap this macro discovery layer |
| `candidate-evolution-source-diversification` | Expand upstream candidate generation beyond static templates |
| `candidate-autonomous-growth-objective-calibration` | Calibrate objective function, exploration budget, and no-regret stop rules |

## Completed Candidate Marker

Speckit contract marker consumed by released-work after this feature ships.

| Field | Value |
|-------|-------|
| `completed_candidate_id` | `candidate-macro-growth-discovery` |
| `status` | `released` after tasks are complete |
