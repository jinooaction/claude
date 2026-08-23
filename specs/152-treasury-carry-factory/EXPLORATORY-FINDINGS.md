# Spec 152 - Treasury Carry Factory Findings

## Frozen experiment

- Official candidates: 64 across carry-roll, carry-rate-trend, defensive-curve, and curve-barbell.
- Prior trials retained: 512; cumulative multiplicity penalty: 576.
- Data: official DGS3MO, DGS2, DGS5, DGS10, and DGS30 observations known by each monthly decision.
- Development/holdout: 1990-2006 development, one-month embargo, 2007-02 onward holdout.
- Safety: long-only, no leverage, no broker call, no order, no capital or whitelist change.

## Local official-data result

The first complete local run used public data through 2026-08-20. All five series, 64 current
trials, 512 prior trials, 576 cumulative trials, unique fingerprints, point-in-time alignment,
freshness, and research/order parity gates passed.

The result was `NO_FACTORY_EDGE`. The provisional best was
`treasury-curve_barbell-dfacba3b4e91`, but it failed DSR (`0.018830 < 0.95`), PBO
(`0.880952 > 0.10`), PSR versus the equal Treasury ladder (`0.677424 < 0.95`), segment win rate
(`0.50 < 0.60`), Sharpe advantage (`0.099378 < 0.20`), and the required Sharpe improvement when
blended 20% with the incumbent three-asset portfolio (`0.021310 < 0.05`).

The candidate did show useful defensive properties: correlation with the incumbent was `0.322005`
and the 80/20 blend reduced maximum drawdown from `17.27%` to `14.11%`. Those properties are not
enough to justify capital because the search-wide overfitting probability remained far above the
pre-registered maximum.

## Decision

Do not arm, allocate capital, widen the whitelist, or submit orders. Publish the complete negative
result and advance the independent search frontier to credit or foreign-exchange carry without
relaxing any threshold or adding post-result Treasury candidates.
