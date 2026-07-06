# Research: Cost-Adjusted Edge Experiment

## Decision 1: Treat cost stress as provisional, not realized execution cost

**Decision**: Calculate simple stress scenarios of 10/25/50 bps against forward total return, but keep `cost-basis-completeness` at `WAIT` unless turnover, accepted/fill data, or explicit realized cost basis is present.

**Rationale**: Current forward sidecar has aggregate returns and drawdowns, not turnover. Current execution-quality sidecar observes `INTENT_LOSS`, rejected orders, parsed KIS errors, and smoke state, but it does not provide enough accepted fill cost basis to convert losses into strategy-level slippage.

**Rejected Alternatives**:

- Treat cumulative intended order mark PnL as realized cost: rejected because intent loss is not equivalent to per-track trading cost.
- Ignore execution-quality entirely: rejected because the autonomous candidate explicitly asks for cost-adjusted edge and execution-quality evidence.

## Decision 2: Add `execution-quality` as a required sidecar

**Decision**: The required input list includes `automation/execution-quality-last-run:LAST_RUN.md` even though the autonomous-work source refs listed five inputs.

**Rationale**: The candidate next action explicitly says to read `execution-quality`. A cost-adjusted experiment without execution-quality would reproduce the same forward-only blind spot.

## Decision 3: Current evidence should wait, not block

**Decision**: Current-style evidence with forward `comparable_count=0`, monitor verdict `INSUFFICIENT_DATA`, and broker rejections should produce `OBSERVATION_WAIT`.

**Rationale**: Evidence exists and is parseable. The system is not broken; it simply has insufficient observations and incomplete cost basis.

## Decision 4: Keep the feature read-only

**Decision**: The probe only reads sidecar snapshots and optional local repository files. It does not query broker APIs, submit orders, alter money-path state, or call external paid services.

**Rationale**: The candidate is a no-live experiment contract. Moving money or changing live behavior would be a different risk grade and would require explicit operator approval.

