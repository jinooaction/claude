# Data Model: Autonomous Sidecar Handoff Liveness Closure

## AgentOpsCompletionEvidence

- `pipeline_liveness_present`: whether the pipeline-liveness surface exists and parses as current evidence.
- `autonomous_evolution_monitored`: whether the surface contains an `autonomous-evolution` check.
- `autonomous_evolution_status`: status of that check when detectable.
- `handoff_present`: whether handoff evidence exists.
- `handoff_entrypoint`: whether the handoff evidence points sessions to local ground truth and `/sync`.

Validation:

- Completion requires `autonomous_evolution_status == OK` and `handoff_entrypoint == true`.
- Missing or malformed evidence must not be treated as complete.

## AgentOpsCandidateState

- `candidate_id`: stable ID `candidate-88a7e7f07361`.
- `status`: `released` when completion evidence is satisfied; otherwise existing candidate status.
- `next_action_ko`: completion message or existing repair action.
- `safe_high_leverage_work_membership`: false when released.

Validation:

- Released candidate must not appear in `safe_high_leverage_work`.
- Regressed evidence must keep or restore actionability.

## ReleasedWorkContract

- `completed_candidate_id`: explicit marker consumed by released-work.
- `source_file`: `specs/086-autonomous-sidecar-handoff-liveness/contracts/agent-ops-liveness-closure.md`.
- `tasks_complete`: all tasks in `tasks.md` checked.

Validation:

- `released_work_probe.py --repo-root .` includes the candidate only after tasks are complete.
