# Data Model: Frontier Candidate Discovery

## Frontier Discovery Candidate

Generated `WorkPacket` emitted by autonomous-work execution when known queues are exhausted.

| Field | Value / Rule |
|-------|--------------|
| `candidate_id` | `candidate-autonomous-frontier-discovery` |
| `domain_key` | `agent_ops` |
| `work_type` | `agent_operating_system` |
| `risk_grade` | 2 |
| `status` | `EXECUTION_READY` until released-work closes this spec |
| `safety_impact` | Empty |
| `required_inputs` | released-work, pipeline-liveness, capital-path-readiness, autonomous-work evidence |

## Closed Queue Summary

| Field | Meaning |
|-------|---------|
| `closed_count` | Number of packets whose status is `RELEASED` or `SUPPRESSED`. |
| `released_count` | Number of closed packets completed through released-work. |
| `suppressed_count` | Number of closed packets suppressed by learning ledger or source status. |
| `macro_released_count` | Number of built-in macro-growth candidates already completed. |

## Completed Candidate Contract

The completion field is named `completed_candidate_id`.
The completed candidate value is `candidate-autonomous-frontier-discovery`.

This marker is consumed by `released_work` only after all task checkboxes in `tasks.md` are complete.
