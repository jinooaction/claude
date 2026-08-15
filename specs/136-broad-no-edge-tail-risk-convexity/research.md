# Research: Broad No-Edge Tail-Risk Convexity

## Decision: Use sidecar-only evidence

**Rationale**: Current money-path is `PREVIEW_ONLY`/`NO_EDGE_YET`; broker access is healthy but investment evidence is not. The fastest safe path is to widen no-live evidence contracts without touching live execution.

**Alternatives considered**:

- Place a live trade to collect evidence: rejected because this bypasses `NO_EDGE_YET`, `latest_intent_loss`, and `armed=false`.
- Pull fresh paid option data: rejected because external paid services are outside the approved safety boundary.

## Decision: Treat tail-risk as a candidate lane, not a trading instruction

**Rationale**: The available sidecars can show where drawdowns and adverse regimes exist, but they do not yet validate a tradable convexity instrument. The contract therefore proposes lanes and gates, not orders.

## Decision: Include execution-quality as a first-class input

**Rationale**: Convexity protection can fail after costs. Current execution-quality evidence also carries `INTENT_LOSS`, so cost drag and rejected-order context must be visible before any later live candidate exists.
