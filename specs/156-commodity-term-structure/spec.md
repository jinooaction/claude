# Feature Specification: Independent Commodity Term Structure

**Branch**: `Codex/156-commodity-term-structure`  
**Created**: 2026-08-25  
**Status**: Corrected v2 preregistered before v2 return evaluation

## Goal

Build an independent commodity term-structure family that estimates whether broad commodity futures are
being paid or charged to roll, then immediately test a frozen 16-candidate family without changing the
gate after seeing results.

## User Stories

### US1 - Test a distinct economic return source (P1)

The operator can test carry earned from the futures curve, separately from equity, bond, credit, FX, and
simple price momentum families.

**Acceptance**: Exactly 16 deterministic candidates are generated from four economic grammars, two signal
lookbacks, and two maximum commodity allocations.

### US2 - Prevent future leakage and source drift (P1)

The operator can reproduce each monthly decision from data that existed then. BlackRock benchmark/fund
series and World Bank spot indices are identified, hashed, dated, and checked for coverage and freshness.

**Acceptance**: A target month uses signal observations through the previous month only; missing, malformed,
stale, shortened, renamed, or mismatched sources fail closed.

### US3 - Separate a weak strategy from an unreasonable gate (P1)

The operator sees the fixed family-size-16 calibration beside the realized holdout result.

**Acceptance**: Null false acceptance remains at most 5%, planted annual Sharpe 0.60 detection remains at
least 80%, and the family result reports every blocking gate rather than only a final label.

### US4 - Preserve useful but unproven candidates without risking capital (P2)

A candidate that clears the preregistered 0.80 paper threshold can continue gathering forward evidence,
while only a 0.95 result that clears all economic gates can become research-canary evidence.

**Acceptance**: `PAPER_CHALLENGER` has no capital, order, deploy config, whitelist authority, or direct path
to live; `FACTORY_EDGE` is still only evidence for a later `Backtest -> Canary -> Full` decision.

## Requirements

> **Grade 4 - money path adjacent**: this feature nominates future investment evidence but cannot place an
> order, allocate capital, arm live trading, add `GSG` to the whitelist, or change constitution/kernel limits.

- **FR-001**: Use official iShares/BlackRock monthly `GSG` fund NAV and S&P GSCI Total Return benchmark
  growth series, plus the World Bank Pink Sheet monthly Total Index spot proxy.
- **FR-002**: Record source URL, provider, units, coverage, latest date, observation count, content digest,
  retrieval time, and citation; do not republish the licensed raw BlackRock series in sidecars.
- **FR-003**: Estimate monthly realized term premium as benchmark total return minus World Bank Total Index
  spot return minus the prior-known three-month Treasury cash return. Treat the Treasury yield as an
  approximation to the index collateral return and composition mismatch as an explicit basis risk.
- **FR-004**: Use each signal with a one-month lag. The return earned in month `t` may only use signals through
  month `t-1`.
- **FR-005**: Generate exactly 16 candidates: `carry_positive`, `carry_momentum`, `carry_rank`, and
  `defensive_carry`; signal lookback 3/12 months; maximum commodity allocation 50/100%.
- **FR-006**: `carry_positive` requires positive rolling carry; `carry_momentum` additionally requires
  positive 12-month benchmark momentum; `carry_rank` requires rolling carry above its trailing 36-month
  median; `defensive_carry` additionally requires 12-month fund volatility no higher than its trailing
  36-month median.
- **FR-007**: Use actual `GSG` fund NAV return when commodity weight is active and three-month Treasury cash
  return when inactive; remain long-only and unlevered.
- **FR-008**: Evaluate 10, 25, and 50 basis-point turnover costs without changing candidates.
- **FR-009**: Use the first 96 usable months for development-only selection, one embargo month, and at least
  120 untouched holdout months. Holdout data cannot alter the selected candidate.
- **FR-010**: Preserve 656 prior unique audit records, add 16, and publish a 672-record global audit catalog;
  use only the current 16 candidates for family statistics.
- **FR-011**: Report effective independent trials, development DSR/PBO, untouched holdout excess PSR,
  50bp economics, incumbent correlation, and 80/20 blend Sharpe/drawdown.
- **FR-012**: `FACTORY_EDGE` requires calibrated gate power, holdout excess PSR >=0.95, positive 50bp annual
  return, incumbent correlation <0.80, blend Sharpe improvement >=0.05, and non-worsening blend drawdown.
- **FR-013**: `PAPER_CHALLENGER` requires holdout excess PSR >=0.80, positive 50bp annual return,
  correlation <0.80, non-declining blend Sharpe, and blend drawdown no worse than 120% of incumbent.
- **FR-014**: Bind the decision to gate, family, objective, candidate, strategy, data, code, split, source,
  and target-weight fingerprints.
- **FR-015**: Emit one of `FACTORY_EDGE`, `PAPER_CHALLENGER`, or `NO_FACTORY_EDGE`, with no threshold,
  grammar, split, or candidate changes after observing the result.
- **FR-016**: Keep capital, orders, cancellations, positions, whitelist, caps, secrets, live arming,
  constitution, and kernel unchanged.

## Edge Cases

- A World Bank revision changes history while the URL stays the same: the digest changes and the audit records it.
- The two providers end in different months: evaluation stops at the last common complete month.
- The BlackRock API schema or benchmark identity changes: fail closed.
- Total return minus spot return is not pure roll yield because index composition and collateral can differ;
  never label it an exact front/second-contract spread.
- No active signal means 100% cash, not a short commodity position.
- `GSG` remains outside the current live whitelist even if the research gate passes.

## Success Criteria

- **SC-001**: Both primary sources cover the common 2006-08 through 2026-07 window with 240 monthly levels.
- **SC-002**: Candidate generation always yields 16 unique IDs and strategy fingerprints.
- **SC-003**: At least 96 development and 120 untouched holdout returns pass point-in-time checks.
- **SC-004**: Production replay reports 672 global trials, 16 local trials, and effective trials in [1, 16].
- **SC-005**: Any failed blocking gate produces no live candidate, no deploy config, no capital, and no order.
- **SC-006**: Focused tests, full pytest, ruff, YAML, strict harness, handoff facts, production replay, deployment,
  and KIS no-order smoke pass before completion.

## Assumptions

- S&P GSCI Total Return minus the World Bank Total Index and cash returns is a broad realized term-structure
  proxy, not a contract-level curve measurement.
- `GSG` NAV is the executable return proxy and includes fees/tracking effects.
- The family is a diversifying sleeve and never replaces the incumbent portfolio by itself.
