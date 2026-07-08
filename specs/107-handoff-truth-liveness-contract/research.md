# Research: HANDOFF Truth Liveness Contract

## Decision: Wrap the existing HANDOFF fact checker

**Rationale**: `scripts/check_handoff_facts.py` already encodes the important rule: latest `origin/main` is accepted, and a first-parent baseline is also accepted when the latest merge only changes Markdown or `specs/` paths. Reusing it prevents two definitions of stale HANDOFF.

**Alternatives considered**:

- Reimplement git baseline parsing inside the new module. Rejected because it would split the truth rule.
- Only document the checker in HANDOFF. Rejected because autonomous-work needs structured completion and next-candidate evidence.

## Decision: Add a read-only analytics report plus CLI probe

**Rationale**: Recent liveness contracts use a module and probe pair so local work, workflows, and tests can all produce the same JSON/Markdown result. This keeps the contract inspectable without creating a write-capable automation.

**Alternatives considered**:

- Add another branch-only sidecar workflow now. Rejected for MVP because the current request is to complete the next candidate, and the repo already has a local probe/release path for validation.
- Extend `agent_harness_probe.py` directly. Rejected because harness health and HANDOFF truth liveness are related but not identical contracts.

## Decision: Treat this as risk grade 2

**Rationale**: The change affects operating-system evidence and autonomous next-work progression, so it must pass SDD, handoff facts, strict harness, and PR quality checks. It does not alter safety gates, money path, secrets, or external API behavior.

**Alternatives considered**:

- Risk grade 1. Rejected because the feature changes next-session behavior and autonomous candidate closure.
- Risk grade 3. Rejected because no safety boundary, constitution, kernel, order limit, secret, or deploy guard is changed.

## Decision: Completion marker advances to PR/merge evidence liveness

**Rationale**: Spec 106 already defined the operating-system frontier order. Once HANDOFF truth liveness is released, the next unreleased operating-system candidate should be `candidate-pr-merge-evidence-liveness-contract`.

**Alternatives considered**:

- Stop after this contract with no next candidate. Rejected because that would reintroduce manual candidate discovery.
- Jump to worktree concurrency liveness. Rejected because PR/merge evidence is the next frontier entry and directly supports autonomous merge reliability.
