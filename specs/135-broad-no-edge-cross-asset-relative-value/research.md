# Research: Broad No-Edge Cross-Asset Relative Value

## Decision: Materialize a no-live contract instead of a live strategy

**Decision**: Add a read-only analytics report and probe for the selected candidate.

**Rationale**: money-path remains `PREVIEW_ONLY`/`NO_EDGE_YET`; the fastest safe path is to widen the candidate search while keeping live orders blocked.

**Alternatives considered**: Re-arm live canary or change portfolio allocation. Rejected because PSR is below threshold and edge-autoarm is `WAIT_EDGE`.

## Decision: Use existing sidecars only

**Decision**: Consume forward paper, public data, regime stratify, money-path, edge-autoarm, released-work, and pipeline liveness.

**Rationale**: These sidecars are already produced by automation and contain enough evidence to define relative-value lanes without adding cost or fresh external calls.

**Alternatives considered**: Pull new market data during the probe. Rejected because this contract must stay deterministic and read-only.

## Decision: Define four lanes

**Decision**: Emit equity/duration, duration/commodity, risk asset/cash proxy, and broad no-edge exclusion lanes.

**Rationale**: These lanes directly match the autonomous-work review axes: `relative_value_spread`, `cash_proxy_yield`, and `asset_pair`.

**Alternatives considered**: Generate a full backtest candidate package. Rejected because this candidate's scope is SDD contract definition; candidate implementation factory can later consume the contract.

## Decision: Completion marker advances to tail-risk convexity

**Decision**: Use `completed_candidate_id: candidate-broad-no-edge-cross-asset-relative-value-experiment`.

**Rationale**: Spec 134 already added second-wave broad no-edge ordering. Once this candidate is released, the next unreleased entry is tail-risk convexity.

**Alternatives considered**: Fall back to wait-for-fresh-evidence. Rejected because the second-wave map still has open candidates.
