# Research: Agent Ops Frontier Map

## Decision: Extend autonomous-work instead of adding a workflow

**Rationale**: The selected work is a Codex work packet selection problem. The existing `autonomous_work_execution` report already owns macro, investment, data, and execution-quality frontier maps, priority ordering, released-work suppression, and Markdown/JSON output. Extending that surface keeps the behavior deterministic and read-only.

**Alternatives considered**:
- Add a new scheduled workflow. Rejected because the current candidate asks for work packet regeneration, not a new sidecar writer.
- Put the operating-system frontier only in HANDOFF. Rejected because autonomous-work must expose machine-readable next-work state.

## Decision: First nested candidate is handoff truth liveness

**Rationale**: The most repeated agent-ops failure in this repository is stale or incomplete handoff state causing the next session to rediscover already-merged facts. A handoff truth liveness contract is the highest-leverage next operating-system candidate after the frontier map itself is released.

**Alternatives considered**:
- PR/merge evidence liveness first. Valuable, but PR quality and merge evidence already have an enforced gate; stale handoff directly affects every session start.
- Worktree concurrency liveness first. Valuable, but the current guard already forces isolation on WARN/BLOCK; handoff truth affects more turns.

## Decision: Use repo-local operating controls as required inputs

**Rationale**: Agent-ops candidates depend on `HANDOFF.md`, `check_handoff_facts.py`, `agent_harness_probe.py`, PR quality workflow, released-work, and autonomous-work evidence. These are not all sidecars, but they are the actual operating controls the next candidate will inspect.

**Alternatives considered**:
- Only include sidecar refs. Rejected because it hides the handoff/harness controls that make the agent-ops candidate meaningful.

## Decision: Preserve all existing priority gates

**Rationale**: Operating-system regeneration must not outrank pipeline repair, normal ready candidates, safety/operator candidates, or blocked recovery. It should only be used when the queue reaches the existing macro-map operating-system frontier state.

**Alternatives considered**:
- Always rank agent-ops candidates when handoff/harness controls exist. Rejected because it would mask investment/data/execution-quality work and recovery candidates.
