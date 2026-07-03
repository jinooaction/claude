# Research: Source Diversification Candidate Closure

## Decision 1: Close through released-work, not ranking heuristics

**Decision**: Use an explicit `completed_candidate_id` marker for `candidate-source-diversification-sidecar-bottleneck`.

**Rationale**: The repository already has a released-work ledger that scans completed Speckit tasks and feeds autonomous work execution. This gives deterministic closure without inventing another suppression surface.

**Alternatives considered**:

- Lower the source diversification candidate score: rejected because the candidate would still be actionable.
- Hard-code a special skip in autonomous work execution: rejected because it would duplicate released-work semantics.

## Decision 2: Treat this as a grade 2 operating automation closure

**Decision**: Classify the work as risk grade 2.

**Rationale**: The change affects what the autonomous system chooses next and what future sessions see, but it does not touch the money path or safety perimeter.

**Alternatives considered**:

- Grade 0 docs-only: rejected because Speckit completion markers are consumed by automation.
- Grade 3 safety change: rejected because no safety boundary, kernel, order, capital, secret, or deployment restriction changes.

## Decision 3: Verify by latest sidecar replay with repo-root override

**Decision**: Validate the current sidecar set by replaying autonomous work execution with `--repo-root .`.

**Rationale**: The latest GitHub run had a same-push sidecar ordering mismatch. Repo-root override proves what the next released-work-aware run will select after this spec is complete.

**Alternatives considered**:

- Wait for the next scheduled workflow only: rejected because it leaves the session without reproducible local proof.
