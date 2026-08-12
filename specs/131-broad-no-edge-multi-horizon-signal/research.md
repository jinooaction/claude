# Research: Broad NO_EDGE Multi-Horizon Signal

## Decision: Use forward sidecar rows as the current tested signal surface

**Rationale**: The selected work packet names `rebalance-paper-forward` as a required input, and that sidecar already exposes track keys, labels, verdicts, observation counts, universes, and the current no-edge posture. This is enough to infer what has already been tested without adding broker or market-data calls.

**Alternatives considered**: Query live strategy configuration or broker holdings. Rejected because this candidate is no-live and must stay inside existing evidence surfaces.

## Decision: Infer signal families and holding periods conservatively

**Rationale**: Current forward rows do not guarantee explicit signal-family or holding-period fields. A conservative deterministic inference from track key, label, universe breadth, incumbent status, and known sidecar context can still identify when the current surface is mostly single-horizon trend/momentum and where new no-live candidates should widen the search.

**Alternatives considered**: Add strategy metadata to every upstream forward track first. Rejected because that would make this slice larger than necessary; explicit metadata can be a later improvement.

## Decision: Propose separated signal candidates across trend, carry, quality, and volatility

**Rationale**: The operator's complaint was that the search was too narrow. The next useful no-live contract should not simply retry momentum. It should name candidates that deliberately span short, medium, and long horizons and include carry, quality, and volatility behavior.

**Alternatives considered**: Add one more momentum-only track. Rejected because it would keep measuring the same kind of no-edge surface.

## Decision: Treat missing regime support as a wait for regime-aware candidates only

**Rationale**: Regime evidence improves volatility and carry validation, but trend/quality signal-family design can still be documented without it. Blocking the whole report would overstate the dependency.

**Alternatives considered**: Require full regime-stratify availability for every candidate. Rejected because it would turn one optional dimension into a hard blocker for the entire no-live contract.

## Decision: Completion marker advances broad no-edge frontier

**Rationale**: This spec completes `candidate-broad-no-edge-multi-horizon-signal-experiment`, not every broad no-edge experiment. Closing this candidate should let autonomous-work advance to `candidate-broad-no-edge-regime-cost-robustness-experiment`.

**Alternatives considered**: Modify broad frontier ordering. Rejected because spec 124 already added release-aware deterministic advancement.
