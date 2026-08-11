# Research: Broad NO_EDGE Frontier

## Decision 1: Keep the parent broad no-edge fingerprint stable

**Decision**: Exclude broad no-edge parent and follow-up candidate IDs from the parent fingerprint source.

**Rationale**: The parent broad candidate is meant to be suppressible by released-work. If the candidate's own release changes the released-work digest, the same situation can produce another parent candidate with a new hash. That would look like progress while actually repeating the same job.

**Alternatives Considered**:

- Remove released-work from the fingerprint entirely: rejected because a small stable release signature still helps distinguish genuinely different exhaustion states.
- Keep current fingerprint: rejected because it can loop after release.

## Decision 2: Add a specific broad no-edge map instead of reusing existing investment-edge map

**Decision**: Add `broad_no_edge_frontier_map` with entries that explicitly cover strategy family, signal family, holding period, asset universe, regime windows, cost sensitivity, and data missing causes.

**Rationale**: Existing nested maps are already closed in the current sidecar. The broad no-edge candidate was created because those known templates were exhausted, so the follow-up needs to be visibly outside that static list.

**Alternatives Considered**:

- Add more entries to the existing investment-edge map: rejected because that blurs the boundary between the closed known map and the new broad expansion.
- Emit only one hard-coded next candidate: rejected because it would not show the full review surface requested by the operator.

## Decision 3: Keep the whole path no-live

**Decision**: Follow-up packets stay grade 2 and carry the existing safety invariants plus explicit no-order, no-live, no-capital language.

**Rationale**: The current money path is `PREVIEW_ONLY` / `NO_EDGE_YET`. The safe way to accelerate is to widen measurement, not to lower the trading gate.

**Alternatives Considered**:

- Re-arm live execution based on urgency: rejected because it would break the edge-confirmation safety boundary.
- Lower the PSR threshold: rejected because it changes the money gate rather than improving evidence.
