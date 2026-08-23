# Research: Independent Credit Spread Carry

## Decision 1 - Use Treasury HQM rather than ICE BofA spreads

**Decision**: Use `HQMCB10YR` and `HQMCB20YR`, sourced from the U.S. Treasury through FRED.

**Rationale**: The HQM curve has monthly public-domain history from 1984 and covers AAA, AA, and A
corporate bonds. ICE BofA FRED history was reduced to three years in April 2026 and its terms prohibit
redistribution, making it unsuitable for this public sidecar and long holdout.

**Alternatives considered**: ICE BofA investment-grade/high-yield OAS; Moody's Baa/Aaa yields; ETF-only
price history. Rejected for shortened history, redistribution restrictions, or unavailable stable CI source.

## Decision 2 - Conservative return representation

**Decision**: Approximate an investment-grade corporate sleeve using prior-month HQM 10-year yield carry
minus duration times the next monthly yield change, with convexity and explicit turnover costs. Use the
existing Treasury model for the defensive sleeve.

**Rationale**: This is point-in-time, reproducible, and avoids pretending a current ETF existed before launch.
It is the same conservative rolling-par approach already used for Treasury carry.

**Alternatives considered**: Backfilled LQD adjusted prices and total-return indices. Rejected because stable,
license-safe deep history is not available in the current production collector.

## Decision 3 - Four frozen signal grammars

**Decision**: Freeze `carry_buffer`, `spread_compression`, `curve_value`, and `stress_reentry` before results.
Cross them with lookback 3/12 months, spread threshold 50/100bp, confirmation 1/3 months, and maximum credit
weight 50/100%, yielding 64 candidates.

**Rationale**: Each grammar expresses a different economic mechanism while staying live-expressible with a
monthly HQM snapshot and long-only `LQD`/`IEF` weights.

**Alternatives considered**: High-yield rotation and ratings buckets. Rejected because they need restricted
or currently unavailable deep data.

## Decision 4 - Keep the calibrated family boundary

**Decision**: Reconstruct the prior 576 unique trials from four explicit sources: 256 production price
candidates in the ledger, 192 exploratory replays and 64 macro candidates in the macro factory evidence,
and 64 Treasury candidates in the Treasury factory evidence. Repeated ledger batches do not count.
Preserve those trials only in the global audit. DSR/PBO use the current 64 candidates;
development is 1990-2006, January 2007 is embargo, and February 2007 onward is untouched holdout.

**Rationale**: This follows spec 153 and avoids both heterogeneous multiplicity inflation and holdout selection.

## Decision 5 - Diversifier objective and no live whitelist change

**Decision**: Predeclare `diversifier`; require holdout blend PSR 0.95, Sharpe improvement 0.05, drawdown
non-worsening, correlation below 0.80, and positive 50bp-cost return. A pass remains research-only because
`LQD` is not in the active live whitelist.

**Rationale**: A credit sleeve should improve the account, while whitelist expansion is a separate safety decision.
