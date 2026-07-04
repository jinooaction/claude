# Research: Investment Edge Frontier Map

## Decision: Treat investment-edge frontier as a nested map, not as the next macro domain

**Rationale**: The prior macro candidate map correctly selected `candidate-investment-edge-frontier-map`. If that candidate is simply released and skipped, the loop would move to data evidence without producing an actual investment experiment candidate. A nested map keeps the loop focused on the operator's stated long-term objective: measured investment performance growth.

**Alternatives considered**:

- Mark `candidate-forward-regime-edge-experiment` as the completed candidate for this spec. Rejected because this spec implements the map and candidate generation, not the experiment itself.
- Skip to `candidate-data-evidence-frontier-map` once investment-edge frontier is released. Rejected because it leaves the investment-edge area unexpanded.

## Decision: Use `rebalance-paper-forward` as the forward verdict input surface

**Rationale**: Existing forward verdict outputs are produced through the forward paper tournament sidecar. The autonomous-work report can consume that sidecar as a read-only evidence surface without running new measurements.

**Alternatives considered**:

- Add a brand-new forward verdict workflow. Rejected because this feature should generate work packets, not create a new experiment runner.
- Use only `money-path`. Rejected because money-path is a top-level live-money state summary and does not expose the full candidate experiment space.

## Decision: First no-live experiment candidate is regime-conditioned forward edge

**Rationale**: Existing repository surfaces already include forward verdicts, regime scoring, money-path state, and released-work memory. A regime-conditioned no-live experiment can be implemented later without broker calls or capital changes, and it directly targets measurable investment edge.

**Alternatives considered**:

- Capital allocation experiment. Rejected because it would be close to the money path and likely higher risk.
- Live canary experiment. Rejected because this feature must remain no-live and SDD-gated.
- Pure operating-system candidate. Rejected because recent work already over-weighted operating-system quality.
