# Research: Paired Forward Edge Gate

## Decision 1: Test active returns for benchmark-relative outperformance

**Decision**: Compute `strategy_return - benchmark_return` for each aligned period and apply PSR/DSR against zero to that active series. Report its annualized ratio as the information ratio.

**Rationale**: The product question is whether the active strategy repeatedly earns return above the investable buy-and-hold benchmark. Information ratio is defined from active return divided by active risk. Pairing keeps the observed covariance instead of pretending the benchmark estimate is fixed.

**Alternatives considered**:

- Keep using strategy PSR against the estimated benchmark Sharpe: rejected because PSR accepts a fixed threshold, while the benchmark Sharpe here is another noisy estimate from the same dates.
- Studentized time-series bootstrap of the exact difference between two Sharpe ratios: statistically robust and retained as a future diagnostic, but it answers a different question and would replace the existing PSR/DSR contract with a heavier bootstrap interface.
- Lower the PSR threshold: rejected. Thresholds remain 0.80 for exploration and 0.95 for full confirmation.

## Decision 2: Preserve absolute quality checks

**Decision**: Continue requiring strategy Sharpe above benchmark Sharpe and positive total excess return, while retaining Calmar and drawdown evidence.

**Rationale**: Active-return significance measures consistent relative gain. It does not by itself prove acceptable absolute volatility, drawdown, or compounded wealth.

## Decision 3: Calibrate before replaying the named strategy

**Decision**: Use a fixed 48-observation correlated scenario, 5,000 repetitions, a null active return, and a preregistered active annual Sharpe of 1.50.

**Rationale**: Forty-eight observations match the current forward evidence scale. Under a correctly calibrated one-sided probability threshold, null acceptance should be about 20% at PSR 0.80 and 5% at PSR 0.95. The planted scenario measures false negatives without tuning to `global-trend-fixed`.

## Primary references

- Bailey and Lopez de Prado, *The Sharpe Ratio Efficient Frontier*: PSR measures the probability that a return series' Sharpe exceeds a specified threshold while accounting for sample length and non-normality.
- Ledoit and Wolf, *Robust Performance Hypothesis Testing with the Sharpe Ratio*: comparing two estimated Sharpe ratios requires inference that respects joint, non-normal, and time-dependent returns; treating one estimate as fixed is not a valid two-strategy comparison.
- CFA Institute performance measurement material: the information ratio evaluates active return relative to benchmark tracking risk.
