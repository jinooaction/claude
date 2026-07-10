# Research: PR/Merge Evidence Liveness Contract

## Decision: Keep the contract read-only and input-driven

**Rationale**: The candidate is an operating-system evidence contract, not a new merge bot. It should structure PR body, merge commit, released-work, and deploy-status observations that already exist. Querying GitHub or SSH inside the analytics module would blur the boundary between reporting and external effects.

**Alternatives considered**:

- Call GitHub APIs from the module. Rejected because the probe must be reproducible in local tests and must not depend on credentials.
- Treat missing deploy evidence as failure. Rejected because deploy observations are naturally post-merge and may be unavailable while the PR is still open.

## Decision: PASS/WAIT/FAIL gates roll up to CONTRACT_READY/OBSERVATION_WAIT/BLOCKED

**Rationale**: The work packet explicitly asks for a PASS/WAIT/FAIL contract. Existing liveness contracts already use `CONTRACT_READY`, `OBSERVATION_WAIT`, and `BLOCKED`, so this feature should match that vocabulary.

**Alternatives considered**:

- Only use boolean ready/not ready. Rejected because it would hide the difference between normal observation lag and broken evidence.

## Decision: Completion marker advances to worktree concurrency liveness

**Rationale**: Spec 106 ordered the agent-ops frontier as HANDOFF truth, PR/merge evidence, then worktree concurrency. Spec 107 already advanced to PR/merge evidence. Once this candidate is released, the next unreleased operating-system candidate is `candidate-worktree-concurrency-liveness-contract`.

**Alternatives considered**:

- Return to macro candidate discovery. Rejected because there is still an open agent-ops frontier entry with higher local continuity.

## Decision: Deploy status evidence is observation text, not a direct deploy checker

**Rationale**: The `/deploy-status` skill names which surfaces are reachable from the container and which require operator-only confirmation. The contract should preserve that distinction by parsing supplied observation text and recording missing evidence as `WAIT`.

**Alternatives considered**:

- Parse GitHub Actions directly. Rejected because connector access belongs to the session workflow, not the deterministic report module.
