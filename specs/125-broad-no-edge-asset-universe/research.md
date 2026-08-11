# Research: Broad NO_EDGE Asset Universe Rotation

## Decision: Use forward sidecar universes as the current tested surface

**Rationale**: The selected work packet names `rebalance-paper-forward` as an input, and that sidecar already exposes track keys, labels, verdicts, observation counts, and universes. This is enough to identify which asset buckets have already been tested without adding broker or market-data calls.

**Alternatives considered**: Query live broker holdings or pull new ETF metadata. Rejected because this candidate is no-live and must stay inside existing evidence surfaces.

## Decision: Classify asset buckets from known symbols deterministically

**Rationale**: Current forward rows include stable ETF symbols such as `SPY`, `QQQ`, `EFA`, `EEM`, `IEF`, `TLT`, `LQD`, `GLD`, `DBC`, `VNQ`, and `UUP`. A small deterministic mapping separates equity, duration bond, credit, commodity, real estate, currency, cash proxy, and unknown exposure without relying on external classification.

**Alternatives considered**: Use an ETF category API or scrape issuer pages. Rejected because external availability changes and this slice only needs a reproducible first contract.

## Decision: Separate defensive rotation candidates from failed wide expansion

**Rationale**: The current `wide` track already tried a broad 11-sleeve expansion and still produced `NO_EDGE`. Repeating that exact idea would not answer the operator's complaint about narrow thinking. The new contract must propose candidates with a different defensive role, such as cash-like Treasury rotation, duration barbell defense, inflation-shock defense, or currency shock defense.

**Alternatives considered**: Add another wider static ETF basket. Rejected because the available evidence says simple wide expansion is already not enough.

## Decision: Treat public-data overall failure as a warning when core macro inputs exist

**Rationale**: Latest public-data has `overall_ok=false` because one cross-check input is absent, but rates and VIX inputs are still published and cross-checked. Asset-universe candidate design can continue with a warning rather than blocking the whole no-live contract.

**Alternatives considered**: Require `overall_ok=true`. Rejected because it would block useful no-live design on a nonessential missing CPI input.

## Decision: Completion marker advances broad no-edge frontier

**Rationale**: This spec completes `candidate-broad-no-edge-asset-universe-rotation-experiment`, not every broad no-edge experiment. Closing this candidate should let autonomous-work advance to `candidate-broad-no-edge-multi-horizon-signal-experiment`.

**Alternatives considered**: Modify autonomous-work ordering. Rejected because spec 124 already added the broad no-edge map and release-aware advancement.
