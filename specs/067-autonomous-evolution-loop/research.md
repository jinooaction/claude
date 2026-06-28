# Research: Autonomous Evolution Loop

## Decision: Build a read-first orchestration layer above existing loops

**Rationale**: The repository already has specialized loops: autonomous tuner for narrow knobs, money-path state for live readiness, opportunity feedback for rejected orders, reassignment for strategy replacement, and pipeline liveness for sidecar freshness. A new loop should not duplicate those decisions. Its value is deciding what to work on next, packaging experiments, and routing proven work into the existing gates.

**Alternatives considered**:

- Directly auto-modify strategies from research ideas. Rejected because it would create a parallel strategy swap path and bypass the reassignment gate.
- Extend only `specs/005-autonomous-tuner`. Rejected because tuner scope is low-risk knobs, not whole-system research and experiment orchestration.
- Chat-only operating guidance. Rejected because it would not leave durable evidence for the next session.

## Decision: Rank by high-leverage breakthrough value, not waiting-time utilization

**Rationale**: The user's clarified goal is a permanent autonomous growth engine, not a tool that only fills idle market-observation time. Candidate scoring must prefer work that can compound profit capacity, evidence quality, capital-path readiness, safety, and learning speed across future runs.

**Alternatives considered**:

- Optimize for whichever task can be done while waiting for market evidence. Rejected because waiting time is only one evidence dependency and would bias the loop toward locally convenient work instead of globally high-leverage breakthroughs.
- Optimize only for immediate profit impact. Rejected because thin evidence, unsafe capital changes, or live-strategy swaps could appear attractive while weakening survival and auditability.

## Decision: Classify safety-boundary and money-path candidates before scoring benefit

**Rationale**: The user wants faster autonomous improvement, but the system must not make "faster" mean "less bounded." Candidates that require orders, capital, whitelist, caps, secrets, paid services, deployment safety, or live strategy swap need a different path before any expected-benefit ranking can matter.

**Alternatives considered**:

- Score all candidates first, then review safety. Rejected because high-upside unsafe candidates could dominate the queue and obscure safe high-leverage work that can proceed inside existing gates.
- Drop unsafe candidates entirely. Rejected because important opportunities like leverage, capital expansion, or new assets should remain visible as operator-review items.

## Decision: Treat stale evidence as an evidence problem, not a strategy problem

**Rationale**: Prior operating issues came from stale or pre-fix sidecars being read as current truth. The evolution loop must first establish freshness and provenance of evidence before drawing conclusions.

**Alternatives considered**:

- Assume latest sidecar contents are current. Rejected because sidecars can be produced by older commits.
- Ignore stale sidecars. Rejected because staleness itself is an actionable operating issue.

## Decision: Use an explicit learning ledger

**Rationale**: The user repeatedly values not doing the same work twice. A ledger with accepted, rejected, evidence-dependent, expired, and recheck states prevents the loop from reintroducing discarded ideas without new evidence.

**Alternatives considered**:

- Use only `HANDOFF.md`. Rejected because handoff is a human entrypoint, not a structured lifecycle record for many candidates.
- Use only GitHub issues. Rejected for the first slice because connector state is less portable than a sidecar artifact and local JSON in tests.

## Decision: First implementation has no LLM calls

**Rationale**: Existing constitution requires LLM calls to be declared judgment points with cost and audit contracts. The first slice can be deterministic by reading existing evidence and applying rules. LLM-assisted research can be a later candidate after a judgment-point contract exists.

**Alternatives considered**:

- Ask an LLM to brainstorm strategies on every run. Rejected because cost, auditability, and hallucination risks are not yet bounded.
- Use LLM only in manual sessions. Accepted as outside the automated first slice.

## Decision: Publish a sidecar and add it to liveness

**Rationale**: The loop is valuable only if it keeps running permanently on every scheduled run. A latest-run sidecar gives the next session a single read path, and liveness prevents silent failure.

**Alternatives considered**:

- Only print workflow logs. Rejected because logs are not the repo's established current-state surface.
- Only update `HANDOFF.md`. Rejected because scheduled automation should not create docs PRs on every run.
