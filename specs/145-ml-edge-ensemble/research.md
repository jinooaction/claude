# Research: Uncertainty-Aware ML Edge Ensemble

## Decision: Start with regularized tabular models, not reinforcement learning

**Rationale**: The clean monthly sample is small. Ridge regression gives a stable baseline and shallow gradient boosting captures nonlinear interactions among momentum, volatility, rates, and inflation. Both are easier to audit and walk forward than a deep policy model.

**Alternatives considered**: Deep neural networks and reinforcement learning were rejected for the first slice because their parameter count, reward design, and repeated trials increase overfit risk without more independent data.

## Decision: Pooled panel prediction across three asset sleeves

**Rationale**: Pooling equity, bond, and gold rows increases training observations while asset identity features preserve sleeve differences. The target is next-month sleeve return, not price level.

**Alternatives considered**: One model per asset was rejected because each would have too few independent labels. Daily ETF data was deferred because long-regime coverage and stable public availability are weaker.

## Decision: Expanding annual refits with a purge gap

**Rationale**: Train only on labels known before each test fold, leave a one-month gap, and test on the next disjoint 12 months. This mirrors an implementable annual model refresh while still producing monthly allocations.

**Alternatives considered**: Random cross-validation is invalid for time series. Monthly refits add computation and correlated model trials without meaningful new independent information.

## Decision: Lower-confidence AI tilt over the incumbent strategy

**Rationale**: Prediction uncertainty combines validation residual dispersion and disagreement between model families. The incumbent trend allocation remains the default; only forecast return above this uncertainty earns an AI tilt. This preserves the existing drawdown behavior when the model has little evidence and uses ML where it can distinguish assets.

**Alternatives considered**: A standalone ML allocation was rejected after the first historical run improved CAGR but worsened stability. Raw forecast-proportional weights and hard top-one selection were rejected because return forecasts are noisy and concentrate model error.

## Current historical result

On the 1971-present public monthly sample, the corrected overlay remains `NO_EDGE`. At 25bp it produced 9.55% CAGR, 2.037 Sharpe, and 5.14% maximum drawdown versus 9.29%, 2.015, and 5.56% for the incumbent. It failed the pre-registered Sharpe-margin, PSR, and fold-win-rate gates, so it is not eligible for live promotion.

## Decision: Pre-register economic and statistical gates

**Rationale**: Candidate readiness requires cost-adjusted out-of-sample improvement over both passive and incumbent trend benchmarks, PSR/DSR significance, fold consistency, and drawdown control. This prevents repeated model search from manufacturing a winner.

**Sources**: Gu, Kelly, and Xiu identify momentum, liquidity, and volatility as leading ML return predictors and emphasize regularization and strict out-of-sample evaluation. Transaction-cost regularization literature shows small costs can reverse portfolio results. The existing project constitution supplies the promotion boundary.
