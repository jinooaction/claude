# Spec 155 Immediate Result

## Frozen Run

- Timestamp: `2026-08-24T00:00:00Z`
- Code identity: `worktree-155` (pre-commit local verification identity)
- Batch: `fx-carry-factory-ccc7cdee7c11`
- Data: Federal Reserve H.10 spot rates and OECD immediate rates delivered by FRED
- Candidates: 16 current-family trials
- Audit: 640 prior + 16 current = 656 unique records
- Development: 203 months through 2006-12
- Embargo: 1 month
- Holdout: 234 months from 2007-02
- Costs: 10/25/50 basis points, frozen before the result
- Live PSR threshold: 0.95, unchanged
- Paper PSR threshold: 0.80, unchanged

## Gate Power

- Family 16 null false acceptance: 0.050
- Family 16 annual Sharpe 0.60 live detection: 0.848
- Family 16 annual Sharpe 0.40 live detection: 0.520
- Family 16 annual Sharpe 0.40 paper admission: 0.790
- The 95% live gate is calibrated but has only about half-power for a modest 0.40 Sharpe.
- `PAPER_CHALLENGER` preserves moderate signals without capital or broker access.

## Strategy Result

- Verdict: `NO_FACTORY_EDGE`
- Development-selected candidate: `fx-pure_carry-a695cb75e58a`
- Holdout PSR versus USD cash: 0.352590
- Holdout excess total return after 50bp costs: -0.11126707
- Incumbent correlation: 0.330163
- 80/20 blend Sharpe change: -0.033920
- Incumbent maximum drawdown: 17.268823%
- Blend maximum drawdown: 15.733094%
- All 16 candidates had negative holdout excess Sharpe; holdout reselection would not rescue the family.

## Defects Found Before Final Run

1. H.10 holiday placeholder rows were counted by collection but treated as missing coverage by the factory.
   Coverage now follows the collection row contract while monthly snapshots independently require usable values.
2. The 3/12-month carry lookback was not applied to pure-carry and carry-value scoring.
   Carry now averages point-in-time rate differentials over the registered lookback.

Neither correction changed a threshold, split, currency, cost, family, or candidate count. The final run started
from the beginning after both corrections. No broker API, order, capital, whitelist, constitution, or kernel changed.
