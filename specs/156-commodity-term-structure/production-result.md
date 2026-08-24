# Production Result: Commodity Term Structure

**Binding replay**: 2026-08-25 UTC, corrected v2 definition, local preregistered code  
**Verdict**: `NO_FACTORY_EDGE`

## Result

- Data: 240 common monthly levels, 2006-08 through 2026-07; source freshness 25 days.
- Family: 16 raw trials, 8.830 effective trials, 656 prior plus 16 current = 672 audit trials.
- Development: 96 months; selected `commodity-carry_rank-9d2f0baf1d27` once, before holdout.
- Embargo: one month.
- Untouched holdout: 142 months, 2014-10 through 2026-07.
- Holdout excess PSR: 0.611866 versus live 0.95 and paper 0.80.
- Annual excess return after 50bp turnover cost: -0.641336%.
- Incumbent correlation: 0.134074.
- 80/20 blend Sharpe change: -0.183303; drawdown improved from 14.842601% to 11.707921%.
- Failed live gates: holdout PSR, positive 50bp economics, and blend Sharpe improvement.
- Failed paper gates: paper PSR, positive 50bp economics, and non-declining blend Sharpe.

## Gate Diagnosis

Family-size-16 calibration has 5.0% null false acceptance and 84.8% detection for a planted annual Sharpe
0.60 signal. The gate is therefore capable of finding a practically meaningful effect. This family's failure
is attributed to weak and unstable realized edge, not an obviously insensitive acceptance threshold.

## Invalidated Plumbing Replay

An earlier local replay omitted the cash subtraction and mixed collateral interest with curve return. Its
PSR 0.757994 is not a valid strategy result, is not included in the 672-record catalog, and cannot support
paper or live promotion. Candidate grammar, costs, split, and thresholds were unchanged for corrected v2.

## Safety and Next Search

Capital 0, orders 0, deploy config null, and GSG whitelist authority false. The next independent family is
commodity inventory and positioning, intended to explain the observed development/holdout regime reversal
without selecting candidates from the holdout.

