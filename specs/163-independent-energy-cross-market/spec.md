# Feature Specification: Independent Energy Cross-Market Factory

**Feature Branch**: `codex/163-independent-energy-cross-market`
**Created**: 2026-08-25
**Status**: Preregistered before candidate inspection; first result frozen; control-description correction recorded without changing behavior
**Input**: Test an independent, directly investable energy timing source and determine whether prior repeated rejection came from weak candidates, objective-mismatched criteria, or a broken gate.

## User Scenarios & Testing

### User Story 1 - Test a direct energy return source (Priority: P1)

As the operator, I can test frozen policies that use crude oil, refined-product, and natural-gas prices to decide whether to hold an energy-equity sleeve or cash.

**Independent Test**: Fixed official source files reproduce the same monthly inputs, 16 candidate identities, expanding-model predictions, and target weights without a broker or order dependency.

**Acceptance Scenarios**:

1. **Given** complete official EIA prices, energy-industry returns, and cash rates, **When** the factory runs twice, **Then** every candidate return, prediction, weight, and fingerprint is identical.
2. **Given** a missing series, wrong workbook identity, future-dated feature, or stale latest source, **When** the factory runs, **Then** it fails before publishing evidence.

### User Story 2 - Separate standalone profit from diversification (Priority: P1)

As the operator, I can judge an energy timing strategy by its declared goal instead of forcing every candidate to improve the existing three-asset portfolio at a fixed 20% blend.

**Independent Test**: The report evaluates a preregistered standalone timing lane and the unchanged legacy diversifier lane side by side, and changing one lane cannot alter the other lane's metrics.

**Acceptance Scenarios**:

1. **Given** a strategy that beats cash and energy buy-and-hold with controlled drawdown, **When** it is highly correlated with the incumbent, **Then** the standalone lane may pass while the diversifier lane fails.
2. **Given** a strategy that improves the incumbent blend but lacks meaningful standalone excess return, **When** it is evaluated, **Then** it cannot pass the standalone lane.

### User Story 3 - Use automation and machine learning honestly (Priority: P1)

As the operator, I can include a simple adaptive model that learns only from information available before each prediction, beside transparent rules that reveal whether the model adds value.

**Independent Test**: Every model training label predates its prediction month, no holdout result changes model settings, and transparent rule candidates remain available as controls.

**Acceptance Scenarios**:

1. **Given** an expanding monthly history, **When** the ridge policy predicts the next energy excess return, **Then** training ends before the prediction feature month and the one-month EIA publication lag is preserved.
2. **Given** candidate results, **When** the report ranks all holdout candidates after the frozen winner is selected, **Then** those ranks are descriptive and cannot authorize promotion.

### User Story 4 - Reach an untouched-holdout verdict now (Priority: P1)

As the operator, I can receive a live-grade, paper-grade, or no-edge verdict immediately from a long untouched period and see exactly which criterion failed.

**Independent Test**: One winner is selected on 120 development months, one month is embargoed, at least 180 later months are evaluated without reselection, and all 736 cumulative trial fingerprints are unique.

**Acceptance Scenarios**:

1. **Given** changed holdout returns only, **When** the factory reruns, **Then** the development winner is unchanged.
2. **Given** no frozen winner passes, **When** a different holdout candidate looks better, **Then** the report discloses it but keeps promotion disabled.

### User Story 5 - Preserve the money boundary (Priority: P1)

As the operator, I can trust that research success does not silently add XLE, allocate capital, arm live mode, or place an order.

**Independent Test**: The module and workflow have no broker/order dependency, and even a passing research result remains ineligible until an exact executable strategy, whitelist authorization, and existing capital consumer contract all pass.

## Edge Cases

- EIA monthly files can have missing cells, changed sheet labels, duplicate dates, unit changes, or a mismatched series identity; all fail closed.
- Petroleum product spot prices are quoted per gallon while crude is per barrel; the crack-spread conversion must use 42 gallons per barrel exactly.
- The historical heating-oil market specification changed in 2013; source lineage and basis risk must be disclosed without rewriting history.
- Monthly EIA averages are not assumed known at month end. Month `t` inputs may first affect energy returns in month `t+2`.
- Current Fama-French industry histories can be revised with CRSP updates. Their source hash must be pinned, and target-return revisions cannot be described as point-in-time fundamentals.
- A model with insufficient training data emits neutral cash exposure; it cannot borrow future labels or shorten the preregistered warm-up after results.
- A policy that is always invested or always in cash cannot pass the exposure-diversity diagnostic.
- A statistically strong candidate that merely recreates energy buy-and-hold without better risk-adjusted performance cannot pass the standalone timing lane.
- A research pass with no exact XLE implementation or authorization cannot reach the capital consumer.

## Requirements

> **Risk and money boundary**: Grade 4 applies because passing evidence can nominate a future research canary. This feature changes research classification, not live capital. It authorizes no order, capital, arming, whitelist, cap, constitution, kernel, or paid-service change. `Backtest -> Canary -> Full` remains mandatory.

### Functional Requirements

- **FR-001**: The system MUST use the fixed EIA monthly series `RWTC`, `EER_EPMRU_PF4_RGC_DPG`, `EER_EPD2F_PF4_Y35NY_DPG`, and `RNGWHHD` for WTI crude, Gulf Coast gasoline, New York heating oil, and Henry Hub natural gas.
- **FR-002**: The system MUST parse the official monthly XLS identity, period, value, unit, source URL, and content hash; incomplete, duplicate, non-positive, or stale data MUST fail closed.
- **FR-003**: The system MUST use the Kenneth French 49-industry value-weighted `Oil` total-return series as the long-history energy-equity research proxy and FRED `DGS3MO` as cash.
- **FR-004**: An EIA observation for month `t` MUST be assumed available only after the end of month `t+1` and MUST first affect the target return for month `t+2`.
- **FR-005**: The system MUST derive four frozen policy families: WTI trend, 3:2:1 refining-margin regime, petroleum/natural-gas breadth, and an expanding ridge forecast.
- **FR-006**: The system MUST generate exactly 16 candidates from four families, 6/12-month feature horizons, and 50/100% maximum energy weights.
- **FR-007**: The ridge policy MUST use only preregistered cross-market returns and the crack margin standardized over the same 6/12-month feature window, a fixed regularization value of 10, at least 60 past labels, deterministic training, and no holdout-driven tuning.
- **FR-008**: Candidate returns MUST hold the energy proxy up to the policy maximum when active, hold three-month Treasury cash for the remainder, and charge 10/25/50bp per turnover.
- **FR-009**: The system MUST select exactly one winner by highest development Sharpe after 25bp, break ties by lower development drawdown and stable candidate identity, embargo one month, and evaluate at least 180 untouched later months without reselection.
- **FR-010**: The standalone live lane MUST require PSR versus cash at least 0.95, annual cash excess after 50bp at least 2%, Sharpe improvement over energy buy-and-hold at least 0.10, maximum drawdown no worse than energy buy-and-hold, and positive energy exposure in 10% to 90% of holdout months.
- **FR-011**: The standalone paper lane MUST require PSR at least 0.80, positive annual cash excess after 50bp, non-declining Sharpe versus energy buy-and-hold, maximum drawdown no worse than 120% of energy buy-and-hold, and positive energy exposure in 10% to 90% of holdout months.
- **FR-012**: The unchanged diversifier lane MUST still report PSR at least 0.95, positive 50bp annual cash excess, incumbent correlation below 0.80, 80/20 blend Sharpe improvement at least 0.05, and non-worsening blend drawdown.
- **FR-013**: The report MUST state that standalone and diversifier lanes answer different objectives; neither lane may silently substitute for the other or retroactively reclassify prior candidates.
- **FR-014**: A real positive control and its mean-zero null MUST demonstrate that the unchanged diversifier lane is passable, while synthetic null false acceptance and planted-signal detection MUST demonstrate that the standalone lane is passable for the actual holdout length and 16-candidate family.
- **FR-015**: The system MUST preserve 720 prior unique audit records and append exactly 16 new unique fingerprints for 736 cumulative records.
- **FR-016**: Output MUST include all candidate metrics, failed gates, development/holdout split, data and model fingerprints, source lineage, objective diagnosis, power, and prohibited post-hoc ranks.
- **FR-017**: Production workflow MUST replace canonical evidence only after exact 16/16 and 736/736 completeness and uniqueness checks pass.
- **FR-018**: No broker import, order path, capital change, whitelist change, external paid API, or result-driven rule, threshold, feature, split, model, or cost change is permitted.
- **FR-019**: XLE is the intended live expression, but a passing backtest MUST remain non-promotable until an exact executable policy, history parity check, live whitelist authorization, and consumer fingerprint match exist.

### Key Entities

- **EnergyMarketObservation**: Series identity, period month, assumed availability month, value, unit, URL, and content hash.
- **EnergyReturnObservation**: Month, energy-industry total return, cash factor, source hash, and proxy limitation.
- **EnergyCrossMarketPolicy**: Family, feature horizon, maximum energy weight, model settings, candidate identity, and strategy fingerprint.
- **EnergyCrossMarketDecision**: Development winner, untouched holdout metrics, standalone and diversifier lanes, controls, power, post-hoc audit, and live-parity state.

## Success Criteria

### Measurable Outcomes

- **SC-001**: At least 301 aligned factor months remain after warm-up, leaving 120 development, one embargo, and at least 180 holdout months.
- **SC-002**: Exactly 16 current trials and 736 unique cumulative audit fingerprints are emitted reproducibly.
- **SC-003**: Every ridge training label predates its prediction month, and repeated identical inputs produce identical model coefficients, predictions, weights, winner, gates, and fingerprints.
- **SC-004**: The latest official data produces a live-grade, paper-grade, or no-edge verdict without any post-result rule change.
- **SC-005**: The report answers separately whether rejection comes from invalid controls, insufficient power, weak standalone economics, failure to improve energy buy-and-hold, failure to diversify the incumbent, or missing live implementation.
- **SC-006**: Focused tests, full pytest, ruff, YAML parsing, strict harness, handoff facts, PR quality gate, production replay, deploy, and no-order KIS smoke complete before closure.

## Assumptions

- EIA monthly spot histories are suitable observable market inputs, but their current files are not revision-vintage archives; the extra publication lag and source hash reduce rather than eliminate revision risk.
- The Kenneth French `Oil` industry portfolio is a long-history research proxy for XLE, not an exact executable return series.
- A directly timed energy sleeve should be judged first against cash and passive energy exposure. Diversification against the incumbent remains useful secondary evidence.
- Ridge regression is intentionally simple and fixed. Its purpose is adaptive weighting of known cross-market features, not unconstrained search.
- A paper or research pass is evidence, not permission to trade.

## Risk Classification

**Grade 4 - money-path evidence classification**. No money movement is authorized by this feature.
