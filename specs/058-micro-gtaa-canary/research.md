# Research: Micro GTAA Live Canary

## Decision: Use `SPYM`, `IEF`, and `GLDM` for the micro live universe

**Rationale**: The existing validated live set (`SPY`, `IEF`, `GLD`) is sound for the capital ladder but weak for a 1,000 USD integer-share micro canary. `SPY` and `GLD` consume too much capital per share, leaving the small account under-diversified. `SPYM` tracks the S&P 500 segment at a lower share price, `IEF` preserves the existing intermediate Treasury leg, and `GLDM` gives lower-unit gold exposure. This makes a three-leg GTAA canary feasible under the manual 1,000 USD cap.

**Alternatives considered**:
- Keep `SPY`/`IEF`/`GLD`: safest continuity, but not enough share granularity for a meaningful micro canary.
- Use `SPLG` instead of `SPYM`: also a low-unit S&P 500 proxy, but the current official State Street `SPYM` page and the user's proposed path favored `SPYM`.
- Use `IAU` instead of `GLDM`: viable fallback and similar gold trust exposure, but `GLDM` is the chosen primary because it is a State Street mini gold product and keeps the gold leg low-unit.

## Decision: Equal-weight GTAA for the micro canary

**Rationale**: Existing research identified the fixed/equal three-asset candidate as a growth-oriented challenger, while the current inverse-vol live strategy is safer but can underuse the micro account. Equal weights also reduce implementation complexity and make each sleeve visible in a small account.

**Alternatives considered**:
- Inverse-vol weighting: preserves validated live style but can concentrate small-account exposure in `IEF`, reducing the "start earning" goal.
- Score-proportional weighting: unnecessary because the three legs are asset sleeves, not competing stock picks.

## Decision: Preserve the multi-speed trend defense

**Rationale**: The user wants maximum return, but the repo's safety model treats survival as the first condition for compounding. Keeping `[63, 126, 189, 252]` trend windows allows exposure to scale down to cash when an asset sleeve loses trend confirmation. This is the same defense principle used by the existing global trend strategy.

**Alternatives considered**:
- Always invested: faster upside capture, but violates the project pattern of avoiding exposure when the trend evidence is absent.
- Single 200-day trend gate: simpler but less responsive than the existing ensemble design.

## Decision: Separate workflow and sentinel

**Rationale**: The capital ladder and existing live canary should remain evidence-gated. A separate `rebalance-micro-gtaa-canary` workflow and `rebalance-micro-gtaa.request` sentinel make the micro experiment obvious, reversible, and independently measurable.

**Alternatives considered**:
- Reuse `rebalance-live-canary.yml`: fewer files, but mixes two different authorities and makes it easier to accidentally weaken the ladder path.
- Direct server command: fastest, but poor forensic record and harder rollback.

## Decision: Manual capital cap stays at 1,000 USD

**Rationale**: This is the smallest practical level for three ETF legs while keeping first-run downside bounded. Larger capital should remain the evidence-gated ladder's job unless the operator explicitly amends the safety perimeter.

**Alternatives considered**:
- 500 USD: safer but likely under-diversified and may miss the equity/gold legs.
- More than 1,000 USD: more meaningful profit potential, but materially expands real-money exposure before the existing evidence gate.
