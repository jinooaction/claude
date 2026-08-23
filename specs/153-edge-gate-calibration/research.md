# Research: Edge Gate Calibration

## Decision 1 - DSR uses one strategy class and effective independent trials

**Decision**: Compute DSR from the current preregistered family and estimate independent trials from
aligned candidate-return correlations. Preserve all prior trials in the audit ledger, but do not pool
heterogeneous price, macro, and Treasury classes into one Sharpe distribution.

**Rationale**: Bailey and Lopez de Prado define the expected maximum over independent trials associated
with a particular strategy class and explicitly warn that using dependent raw trials overstates the
expected maximum. The current 576-row implementation violates both conditions.

**Sources**:
- https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- https://doi.org/10.2139/ssrn.2460551

**Alternatives considered**:
- Keep raw 576: rejected because strategy classes, benchmarks, and return distributions differ.
- Delete prior trials: rejected because it hides research history and weakens auditability.
- Set trial count to one: rejected because 64 configurations were actually searched.

## Decision 2 - PBO stays inside one candidate selection process

**Decision**: Build CSCV/PBO from the current family's development returns only.

**Rationale**: The PBO paper defines N alternatives considered by one strategy-selection process and
describes a family of specifications and parameters run over the same time partitions. Prior families
were not alternatives in the current Treasury selection and cannot share its CSCV ranking matrix.

**Sources**:
- https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- https://escholarship.org/uc/item/4w1110bb

**Alternatives considered**:
- Global PBO over all research ever run: rejected because rows do not represent the same choice set.
- Remove PBO: rejected because family-level selection overfit remains a real risk.

## Decision 3 - selection on development, confirmation on untouched holdout

**Decision**: Rank and freeze one candidate using pre-2007 development data. Skip one month, then use
2007 onward only to confirm the frozen candidate.

**Rationale**: The existing code names 2007 onward a holdout but selects the maximum Sharpe inside that
period. This makes it another training set. DSR/PBO cannot repair a holdout that was used for selection.

**Alternatives considered**:
- Keep holdout selection and add more penalties: rejected because contamination is procedural.
- Repeated rolling reselection: deferred to a separately preregistered walk-forward strategy family.

## Decision 4 - preserve thresholds, separate evidence roles

**Decision**: Report development DSR 0.95 and PBO 0.10 as discovery diagnostics, and keep untouched
holdout PSR 0.95 as the final statistical confirmation. Economic metrics belong to one preregistered
objective route.

**Rationale**: Fixed-seed calibration showed that requiring development DSR 0.95, PBO 0.10, and holdout
PSR 0.95 together detected only about 8% of a persistent annual Sharpe 0.60 edge. Selecting on development
and requiring untouched holdout PSR 0.95 detected above 80% while null false acceptance remained below
5%. DSR and PBO remain visible selection-stability warnings rather than duplicating confirmation.

## Decision 5 - calibrate both type I and type II error

**Decision**: Block activation unless a fixed-seed null simulation has at most 5% false accepts and a
fixed annual Sharpe 0.60 planted-edge simulation has at least 80% detection over 200 repetitions.

**Rationale**: A gate that only demonstrates rejection has unknown usefulness. Planted-edge tests prove
that realistic signal can survive, while null tests prove the correction did not simply loosen standards.

**Alternatives considered**:
- Hand-picked passing fixture only: rejected because it does not estimate error rates.
- Tune thresholds until historical Treasury passes: rejected as direct overfitting.

## Decision 6 - Treasury carry is a diversifier objective

**Decision**: Predeclare the Treasury family as `diversifier`. It must improve the existing portfolio's
80/20 blend Sharpe by 0.05, not worsen drawdown, stay below 0.80 correlation, and remain profitable at
50 basis points. Standalone ladder comparisons remain visible diagnostics.

**Rationale**: The original Treasury specification says the account-level purpose is diversification,
but simultaneously requires every standalone replacement condition. One candidate should be judged by
the role it is meant to perform.
