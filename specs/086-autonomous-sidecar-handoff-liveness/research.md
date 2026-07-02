# Research: Autonomous Sidecar Handoff Liveness Closure

## Decision: Treat this as a completion/duplication closure, not a duplicate implementation

**Rationale**: `pipeline_liveness.default_specs()` already contains `autonomous-evolution`, and `HANDOFF.md` already instructs new sessions to start from local git truth and `/sync`. The remaining failure is that `evolution_loop` does not convert those satisfied facts into a non-actionable agent-operations candidate.

**Alternatives considered**:

- Add `autonomous-evolution` to pipeline-liveness again. Rejected because it is already present and tested.
- Only add a `completed_candidate_id` marker. Rejected because a future scan would still generate the same candidate until released-work catches up.
- Delete the agent_ops candidate entirely. Rejected because if liveness or handoff evidence regresses, the candidate should surface the failure.

## Decision: Use evidence-derived completion status

**Rationale**: The candidate is safe to suppress only when both facts are true: `pipeline-liveness` reports `autonomous-evolution` as OK, and HANDOFF is a real entrypoint with `/sync` guidance. This keeps the loop fail-open for missing evidence.

**Alternatives considered**:

- Hard-code the candidate as released forever. Rejected because it would hide future liveness/handoff regressions.
- Depend only on released-work. Rejected because released-work is a downstream sidecar and can lag one push.

## Decision: Keep safety grade at 2

**Rationale**: The change affects autonomous work selection and next-session behavior, which is operating-system behavior. It does not touch trading safety controls, broker access, real orders, capital, live strategy, whitelist/caps, secrets, paid services, constitution, or kernel manifest.

**Alternatives considered**:

- Grade 1. Rejected because autonomous candidate selection and handoff behavior are operating controls.
- Grade 3. Rejected because no safety perimeter or secret/deploy safety guard changes.
