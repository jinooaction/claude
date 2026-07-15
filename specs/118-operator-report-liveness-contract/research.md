# Research: Operator Report Liveness Contract

## Decision: Add a read-only report module, not a new merge gate

**Rationale**: The existing PR quality gate and strict harness already block missing process evidence. The gap is the operator-facing final meaning layer. A read-only report module can classify that layer without changing merge mechanics or requiring external state.

**Alternatives considered**:

- Extend `scripts/check_pr_quality_gate.py`: rejected because PR body quality and final operator report are related but distinct surfaces.
- Add an LLM judge: rejected because this contract must be deterministic, local, cheap, and reproducible.

## Decision: Treat final-report text as supplied evidence

**Rationale**: Chat history is not a repository artifact. A probe can accept the final-report text from workflow capture, PR comment export, or a manual file. Missing supplied text means observation wait, not contract failure.

**Alternatives considered**:

- Scrape chat/session logs: rejected because it couples the repository to local session storage and privacy-sensitive context.
- Require the PR body to be the final report: rejected because final reports often include post-merge and handoff facts that are not known at PR creation.

## Decision: Keep semantic checks deterministic

**Rationale**: The contract should prevent the known failure mode where the report lists hashes/tests but omits meaning. Keyword and section-shape checks are blunt but reproducible and easy to redteam.

**Alternatives considered**:

- Score prose with a rubric model: rejected due to cost, non-determinism, and no existing LLM judgment point for this workflow.
- Require one exact template: rejected because good final reports vary by task size; the invariant is the meaning categories, not identical formatting.
