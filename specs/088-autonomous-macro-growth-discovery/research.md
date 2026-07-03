# Research: Autonomous Macro Growth Discovery

## Decision: Synthesize macro candidates in autonomous work execution

**Rationale**: `autonomous_work_execution` already consumes the surfaces that define the actual next-work truth: released-work, learning ledger, evolution backlog, capital-path readiness, and pipeline liveness. Adding the closed-queue rule here fixes the observed failure where `ranked_work=0` but `selected_work` still points at a released candidate.

**Alternatives considered**:

- Add released-work as a new input to `evolution_loop`: rejected for this slice because it would broaden evolution evidence freshness behavior and fixture expectations before the immediate selection bug is fixed.
- Add a new workflow: rejected because it would create another sidecar to reconcile rather than using the existing next-work decision point.

## Decision: Generate only when the regular queue is closed

**Rationale**: Macro discovery is a fallback for candidate-space exhaustion. It must not compete with normal execution-ready work, operator approval work, or repair work.

**Alternatives considered**:

- Always rank macro candidates with a lower score: rejected because a scoring bug could hide real recovery or safety work.
- Generate macro candidates when operator approval exists: rejected because approval-required states are intentional safety signals, not empty queue states.

## Decision: Use an ordered macro candidate backlog

**Rationale**: The first candidate bootstraps this feature. After it is released, the loop should still surface a next macro action instead of returning to "nothing to do". A short ordered backlog keeps the behavior deterministic and auditable.

**Alternatives considered**:

- Generate a new hash from current evidence every run: rejected because it would create noisy, hard-to-release candidates.
- Emit only the bootstrap candidate: rejected because it closes this PR but leaves the next session with the same empty-queue problem.

## Decision: Keep all macro candidates risk grade 2

**Rationale**: These candidates alter Codex operating behavior and next-session work selection, so they are not grade 1. They do not touch money, secrets, kernel, constitution, live strategy, whitelist/caps, orders, or external paid services, so grade 3/4 is not appropriate.

**Alternatives considered**:

- Treat as grade 1 code change: rejected because autonomous next-work selection is an operating-system behavior.
- Treat as grade 3 safety change: rejected because no safety perimeter file or money guard changes.
