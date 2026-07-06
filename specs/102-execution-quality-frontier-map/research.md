# Research: Execution Quality Frontier Map

## Decision 1: Model execution-quality as a nested frontier map

**Decision**: Add `execution_quality_frontier_map` beside the existing macro, investment-edge, and data-evidence maps.

**Rationale**: The selected autonomous candidate asks for a map, not a one-off diagnostic report. A nested map preserves the current macro selection pattern and gives released-work a deterministic way to advance from the frontier candidate to narrower execution-quality candidates.

**Alternatives considered**: Add one immediate execution-quality diagnostic candidate only. Rejected because the next session would still need to rediscover the rest of the execution-quality frontier by hand.

## Decision 2: First candidate is broker rejection taxonomy

**Decision**: The first generated execution-quality candidate is `candidate-broker-rejection-taxonomy-contract`.

**Rationale**: Current execution-quality evidence already shows rejected orders, parsed KIS errors, `APBK1672` counts, and live intent-loss gating. A broker rejection taxonomy contract is the narrowest next read-only step: it can classify and audit the observed failure surface without retrying orders or changing capital.

**Alternatives considered**: Start with slippage/latency cost basis. Rejected for first position because current sidecars have stronger rejection/error evidence than accepted-fill cost basis evidence.

## Decision 3: Register broker diagnostic sidecars as autonomous-work inputs

**Decision**: Add `execution-quality`, `kis-smoke`, and `rebalance-micro-gtaa` to autonomous-work consumed sidecars.

**Rationale**: The macro work packet mentions execution-quality and broker diagnostics, but the current manifest only carries generic macro refs. Adding these read-only refs makes the generated candidate reproducible from sidecar evidence rather than hidden operator knowledge.

**Alternatives considered**: Use only `pipeline-liveness` plus `released-work`. Rejected because freshness alone does not explain what execution-quality evidence the next candidate should consume.

## Decision 4: Completion advances within execution-quality before agent-ops

**Decision**: Once `candidate-execution-quality-frontier-map` is released, autonomous-work should select the first unreleased execution-quality frontier entry before moving to the agent-ops macro area.

**Rationale**: The macro map orders execution-quality above agent-ops after investment-edge and data-evidence are closed. Preserving that order avoids skipping the domain that the autonomous loop explicitly selected.

**Alternatives considered**: Treat the frontier map as complete and move directly to `candidate-agent-ops-frontier-map`. Rejected because it would close the area map without creating any actionable execution-quality candidate.

