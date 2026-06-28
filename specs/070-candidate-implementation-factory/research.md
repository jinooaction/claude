# Research: Candidate Implementation Factory

## Decision 1: Use deterministic packages, not LLM-generated strategies

**Decision**: The factory classifies candidates and emits packages from a fixed mapping. It does not ask an LLM to create trading rules or mark results as successful.

**Rationale**: Promotion evidence affects the path toward trading. Generated strategy logic without deterministic validation would weaken the safety ladder.

**Alternatives considered**:
- Generate new rule files directly: rejected because it risks inventing unvalidated strategies.
- Mark all non-trading candidates as passed: rejected because promotion scan would interpret them as strategy-ready.

## Decision 2: Enrich backlog rather than changing promotion loop semantics broadly

**Decision**: The factory writes `candidate_backlog.enriched.json`. Promotion scan consumes this enriched backlog when available.

**Rationale**: Existing promotion stages already express the strategy ladder. Feeding enriched evidence is lower risk than adding broad new stages.

**Alternatives considered**:
- Add many new promotion stages: deferred because actions currently only need forward/canary-ready strategy candidates.
- Patch the evolution sidecar branch: rejected because the factory should publish its own source of truth.

## Decision 3: Pass requires three explicit machine fields

**Decision**: `historical_backtest`, `recent_oos`, and `walk_forward` only become `pass` when result evidence for the candidate sets each field to a pass-like value.

**Rationale**: This prevents old markdown, vague wording, or unrelated pass tokens from promoting every candidate.

## Decision 4: Workflow order is evolution -> factory -> promotion -> actions

**Decision**: The new workflow runs after autonomous evolution and before autonomous promotion. Promotion scan fetches factory sidecar first and raw evolution sidecar second.

**Rationale**: This makes the loop permanent. The next daily promotion scan can see newly merged evidence without operator intervention.
