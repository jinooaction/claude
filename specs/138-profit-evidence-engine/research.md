# Research: Profit Evidence Engine

## Decision: Replace open-ended candidate prose with a small pre-registered search

**Rationale**: The current loop completed multiple `PROPOSED` contracts without generating deployable settings. A fixed 12-candidate set is large enough to test meaningful trend/allocation choices and small enough to audit. Each candidate maps to an existing production factor implementation.

**Alternatives considered**: Unbounded parameter optimization was rejected because it would maximize backtest overfitting. Continuing static no-edge contract lanes was rejected because it already produced no executable result.

## Decision: Select before 2007 and evaluate once from 2007 onward

**Rationale**: A fixed temporal holdout prevents the selected candidate from seeing the global financial crisis, COVID shock, and 2022 stock/bond drawdown during selection. This is stronger than ranking all variants on the full sample.

**Alternatives considered**: Random cross-validation was rejected because market observations are time ordered. Selecting on the full sample and merely reporting subperiods was rejected because the subperiod would no longer be a true holdout.

## Decision: Charge 50bp annual drag and require parameter-neighbor robustness

**Rationale**: The candidate must survive a conservative recurring drag and should not depend on one exact trend window. The selected allocation family must retain Sharpe and drawdown superiority in adjacent registered windows.

**Alternatives considered**: Zero-cost comparison was rejected as economically optimistic. A single winning parameter was rejected as fragile.

## Decision: Keep forward PSR and hardened canary as independent gates

**Rationale**: Long-run trend evidence is economically plausible and broad: Hurst, Ooi, and Pedersen report positive trend-following returns across decades and crisis periods. However, Bailey and Lopez de Prado show that strategy searches inflate performance unless selection bias and nonnormality are controlled. Therefore historical holdout can identify a candidate, but cannot itself declare live readiness.

**Primary sources**:

- Hurst, Ooi, Pedersen, "A Century of Evidence on Trend-Following Investing": https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
- Bailey, Lopez de Prado, "The Deflated Sharpe Ratio": https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

**Alternatives considered**: Combining historical and forward samples into one optimistic statistic was rejected because the samples answer different questions. Lowering the current 0.95 forward threshold was rejected because it would weaken the existing money safety path.

## Decision: Preserve mixed evidence by axis

**Rationale**: `deep_walk_forward_probe.py` currently reports a long-history `RETURN_EDGE`, while the recent portfolio walk-forward can report no edge. The executor collapses both commands to the first JSON verdict and sets all three evidence fields to fail. This destroys information and makes the learning ledger permanently reject economically plausible candidates.

**Alternatives considered**: Letting any one pass dominate was rejected as unsafe. Letting any one fail dominate was rejected as the current bug. Mixed evidence is therefore pending, with each axis retained.

## Decision: Prioritize the fixed-weight three-asset trend candidate

**Rationale**: A local replay using the fixed split found that 3-asset fixed-weight trend variants across 6, 8, 10, and 12-month windows all improved holdout Sharpe and drawdown versus equal-weight buy-and-hold; the 6/8/10-month variants also improved holdout CAGR. The existing forward `globalfixed` track is the strongest current matching candidate by PSR (0.827270) but has not reached 0.95.

**Alternatives considered**: The inverse-volatility live candidate has the strongest long-run risk-adjusted metrics but underperformed holdout CAGR in several windows and has weaker current forward PSR. Immediate live reassignment was rejected because `globalfixed` remains `NO_EDGE` in forward evidence.
