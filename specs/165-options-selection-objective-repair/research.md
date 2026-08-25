# Research: Options Selection and Objective Repair

## Decision 1: Use WPUT as the independent construction

- **Decision**: Use Cboe's WPUT index as the independent replay series.
- **Rationale**: PUT and WPUT express cash-secured SPX put-writing with different rebalance frequencies. WPUT therefore changes the option path while keeping the broad economic thesis comparable.
- **Rejected alternatives**: BXM changes the payoff from put-writing to covered calls; PUTY has a different target; vendor data adds cost and licensing uncertainty.
- **Control**: WPUT never participates in selection, threshold tuning, tie-breaking, or candidate generation.

## Decision 2: Preserve the same 16 candidates

- **Decision**: Re-evaluate the released 16 candidates with unchanged identifiers, parameters, and fingerprints.
- **Rationale**: The task is to repair selection and objectives, not to create another post-hoc strategy family.
- **Rejected alternative**: Adding parameter variants after seeing PUT results would increase researcher degrees of freedom and make the repair untestable.

## Decision 3: Use nested expanding-window selection

- **Decision**: Outer folds use 84 training months, one embargo month, and 12 test months. Every outer training segment contains inner folds with 48 training months, one embargo month, and 12 validation months.
- **Rationale**: Candidate choice must be made using data strictly before each outer test interval. Multiple inner folds expose whether a choice is stable across time rather than lucky in one development window.
- **Rejected alternative**: Reusing the existing development/holdout split preserves the single-winner and repeated-holdout defect.

## Decision 4: Use lexicographic selectors

- **Decision**: Portfolio selection orders candidates by worst inner cash-excess Sharpe, median cash-excess Sharpe, median equity-relative Sharpe improvement, median tail advantage, then candidate ID. Timing selection uses the analogous statistics versus the same-weight passive candidate and excludes passive variants.
- **Rationale**: A fixed lexicographic order is deterministic and avoids tuning a weighted score after seeing outcomes.
- **Rejected alternative**: Optimized score weights introduce another hidden hyperparameter search.

## Decision 5: Separate the economic questions

- **Decision**: Publish three independent lanes: premium existence, portfolio adoption, and timing value.
- **Rationale**: A put premium can beat cash yet fail to improve a broad-equity portfolio. Treating those as one gate was a category error.
- **Control**: No lane can promote the strategy from historical data. Every lane records `promotion_eligible=false`.

## Decision 6: Review the entire system on two readiness axes

- **Decision**: Review data, strategy research, statistical validation, forward evidence, execution, risk/order controls, and automation/operations. Report order-automation readiness separately from profit-edge readiness.
- **Rationale**: Reliable order plumbing cannot substitute for a validated edge, and an attractive backtest cannot substitute for executable and reconciled orders.
- **Control**: Findings are ranked by money-path impact and backed by code, test, sidecar, or production-probe evidence.
