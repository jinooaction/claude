# Preregistered Latest-Data Result

**Observed**: 2026-08-25 after the spec, candidates, split, costs, and gates were frozen.

## Complete Gate Audit

- Verdict: `FULL_GATE_CONTROLS_VALID`
- AQR diversified TSMOM after 50bp: PSR `0.962691`, annual excess `4.580010%`, incumbent correlation `-0.124257`, 80/20 blend Sharpe improvement `0.170016`, blend drawdown `11.261123%` versus incumbent `17.268823%`.
- Demeaned null after 50bp: PSR `0.434559`, annual excess `-1.373408%`, blend Sharpe improvement `-0.042803`; complete verdict failed.
- Conclusion: the complete promotion standard is empirically passable. Spec 157's PSR-only audit was incomplete, but the remaining economic gates are not an impossible barrier.

## Supply-Demand Family

- Candidate count: 16; global unique audit records: 704.
- Development winner: `commodity-supply-demand-synchronized_balance-fc61d460f7f2`.
- Holdout: 142 months, 2014-10 through 2026-07, with no reselection.
- Result: `NO_FACTORY_EDGE`; diagnostic class `ECONOMICALLY_PROMISING_STATISTICALLY_UNCONFIRMED`.
- Passed: 50bp annual excess `+0.447504%`, correlation `-0.135530`, blend Sharpe improvement `+0.118590`, and drawdown non-worsening.
- Failed: holdout excess PSR `0.705637 < 0.95`; paper PSR `0.705637 < 0.80`.
- Safety: no broker API, order, capital, arming, whitelist, constitution, or kernel change.

## Interpretation

This is materially better than prior negative-return candidates, but it is not enough evidence for capital. Lowering the paper threshold after seeing `0.705637` would be result-driven fitting. The next independent test is cross-market or USDA crop supply-demand replication, not repeating these 16 policies.
