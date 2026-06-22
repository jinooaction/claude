# Research: Agent Quality Redteam Harness

## Decision: Extend the existing static harness instead of replacing it

**Rationale**: Spec 056 already provides `scripts/agent_harness_probe.py --strict`, PR-body evidence,
and a task-suite validation pattern. Extending it keeps one command and one PR surface.

**Alternatives considered**:
- Separate benchmark runner: too large for this slice and would require model execution design.
- More prose in `AGENTS.md`: does not make quality measurable.

## Decision: Validate quality and redteam task coverage before model trajectory replay

**Rationale**: The immediate gap is that the operating system has no named regression cases for shallow
first responses and redteam traps. A task-suite contract is a stable foundation for later replay.

**Alternatives considered**:
- Build full multi-agent replay now: useful but larger than necessary and harder to verify in CI.
- Only add redteam prose: easy to ignore and not testable.

## Decision: Add a standalone HANDOFF fact checker and wire it into the harness

**Rationale**: Stale `HANDOFF.md` has repeatedly caused session confusion. A standalone checker is easy
to test with temporary files and can be reused by handoff workflows.

**Alternatives considered**:
- Rely on `/sync` report only: useful interactively but does not fail CI or PR checks.
- Generate all of `HANDOFF.md`: larger migration; this slice validates the most failure-prone rows.

## Decision: Ignore local Codex config and root generated JS bundles

**Rationale**: The observed dirty files are local runtime/config artifacts, not source. They pollute
git truth and local concurrency snapshots.

**Alternatives considered**:
- Delete only current files: one-time cleanup without preventing recurrence.
- Commit them: would add generated/private local state to source control.
