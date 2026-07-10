# Research: Worktree Concurrency Liveness Contract

## Decision: Use read-only synthetic guard evaluation

**Decision**: Import `scripts/local_concurrency_guard.py` and call its in-memory `evaluate` behavior with synthetic `CurrentState` and `Lease` objects. Do not run `--mode isolate`, do not write leases, and do not create worktrees from the report module.

**Rationale**: The feature must prove WARN/BLOCK semantics without mutating `.codex/state/concurrency` or changing local worktrees. Synthetic evaluation keeps the report deterministic and safe in tests, local runs, and CI.

**Alternatives considered**:

- Run real guard modes in a temporary checkout: closer to production but adds filesystem mutation and setup complexity.
- Inspect source strings only: safer but too weak to prove current behavior.

## Decision: Treat runtime guard output as optional evidence

**Decision**: The probe may read supplied guard output text, but absence of that output is `WAIT`, not `FAIL`.

**Rationale**: `.codex/state/concurrency` is gitignored and session-specific. A clean CI checkout may have no runtime lease state. The contract should fail only when static wiring or deterministic guard behavior is broken.

**Alternatives considered**:

- Require a live `local_concurrency_guard.py --mode check` output: too brittle for CI and clean clones.
- Ignore runtime output entirely: loses a useful observation surface for local debugging.

## Decision: Add the next agent harness regression liveness candidate

**Decision**: When worktree concurrency liveness is released, autonomous-work should advance to `candidate-agent-harness-regression-liveness-contract`.

**Rationale**: The existing agent-ops frontier would otherwise be exhausted and selected_work can fall back to a closed released candidate. The harness already has evaluation, first-response quality, and redteam suites; a liveness contract for those suites is the next concrete operating-system candidate.

**Alternatives considered**:

- Leave no next candidate: repeats a known confusion pattern where closed work appears as selected work.
- Reopen older macro candidates: would mix domains and make the agent-ops frontier less reproducible.

## Decision: Recovery snapshot is verified by source surface and optional runtime path

**Decision**: Verify the source contains `write_snapshot`, `SNAPSHOT_DIR`, and output names `metadata.json`, `worktree.diff`, `index.diff`, and `untracked`. Treat the runtime directory as optional evidence.

**Rationale**: The snapshot code is the reproducible contract; local runtime artifacts are intentionally untracked and may not exist.
