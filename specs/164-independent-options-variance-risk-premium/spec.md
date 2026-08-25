# Feature Specification: Independent Options Variance Risk Premium

**Feature Branch**: `Codex/164-independent-options-variance-risk-premium`
**Created**: 2026-08-26
**Status**: Preregistered before candidate return inspection
**Input**: Test a well-known options insurance-premium strategy family, prove whether the objective gate recognizes a real risk premium, and audit whether prior candidates were rejected for weak evidence or misrouted criteria.

## User Scenarios & Testing

### User Story 1 - Test a recognized options risk premium (Priority: P1)

As the operator, I can test cash-secured S&P 500 put-writing exposure using the official Cboe PUT return index rather than another indirect price-trend proxy.

**Independent Test**: Fixed official source files reproduce the same monthly PUT, volatility, market, cash, candidate-weight, and return records without a broker or order dependency.

**Acceptance Scenarios**:

1. **Given** complete official Cboe, Fama-French, and Treasury-rate sources, **When** the factory runs twice, **Then** all aligned observations, 16 candidate identities, returns, and fingerprints are identical.
2. **Given** a malformed index file, missing month, impossible level, stale source, or future feature, **When** the factory runs, **Then** it fails before evidence publication.

### User Story 2 - Judge premium harvesting by its actual objective (Priority: P1)

As the operator, I can tell whether put-writing earns a robust cash premium with better risk-adjusted results than equities, without requiring an always-on risk premium to behave like a market-timing strategy.

**Independent Test**: The report separates standalone premium harvesting from optional timing enhancement, and the timing lane cannot veto an otherwise valid always-on premium candidate.

**Acceptance Scenarios**:

1. **Given** an always-on put-writing candidate that beats cash and improves equity Sharpe, drawdown, and expected shortfall, **When** timing activity is 100%, **Then** the standalone lane may pass while timing enhancement is not applicable.
2. **Given** a dynamic candidate that beats cash but does not improve its matching passive PUT allocation, **When** evaluated, **Then** standalone and timing conclusions remain distinct.

### User Story 3 - Use adaptive timing without future leakage (Priority: P1)

As the operator, I can compare transparent variance-premium and tail guards with a simple expanding model trained only on already known labels.

**Independent Test**: Every implied-versus-realized variance input uses only information available at the prior month end, and every model label predates its prediction month.

**Acceptance Scenarios**:

1. **Given** daily VIX and market returns through month `t`, **When** a target is set, **Then** it may affect PUT exposure only in month `t+1`.
2. **Given** changed holdout returns, **When** the factory reruns, **Then** model settings and the development winner remain unchanged.

### User Story 4 - Audit the gate and prior strategy adoption (Priority: P1)

As the operator, I can see whether a recognized PUT reference, a mean-zero null, and planted synthetic edges are classified sensibly, and whether any of the prior 736 audited candidates was lost solely through objective misrouting.

**Independent Test**: The report emits real-reference, null, and selection-power diagnostics plus a prior-family adoption table; no historical holdout winner can be retroactively promoted.

**Acceptance Scenarios**:

1. **Given** a known PUT reference and its mean-zero null, **When** the gate runs, **Then** both outcomes and every failed criterion are disclosed without forcing either result.
2. **Given** prior sidecar decisions, **When** the adoption audit runs, **Then** it distinguishes negative economics, statistical uncertainty, post-hoc-only promise, forward-evidence absence, and objective misrouting without changing prior verdicts.

### User Story 5 - Produce an immediate safe verdict (Priority: P1)

As the operator, I receive a live-grade, paper-grade, reference-only, gate-suspect, or no-edge verdict now, while capital and order paths remain unchanged.

**Independent Test**: One development winner is frozen before at least 120 holdout months, all 752 cumulative fingerprints are unique, and even a pass lacks live eligibility without exact executable parity.

## Edge Cases

- Cboe index CSV headers, date formats, duplicate rows, or index-level columns can change; unrecognized structure fails closed.
- PUT is a hypothetical benchmark index with collateral and roll rules, not an executable fill history; fees, taxes, assignment, margin, and implementation gaps must remain explicit.
- VIX is an annualized implied-volatility measure while realized variance comes from daily market returns; both must be converted to annualized variance before subtraction.
- Month-end VIX and realized variance through month `t` may only set exposure for month `t+1`.
- Cboe PUT already includes its benchmark roll mechanics. Additional implementation haircuts must not be described as the index's internal trading cost.
- Fama-French market return is a broad-equity research proxy rather than exact SPX total return; basis risk must be disclosed.
- An always-on premium candidate is valid for the standalone lane but is not evidence that timing automation adds value.
- Short-volatility strategies can show smooth average returns and severe tail loss. A candidate cannot pass without drawdown and 95% expected-shortfall controls.
- A post-hoc best candidate or a previously rejected family cannot be promoted after holdout inspection.
- A research pass cannot add PUTW, SPX options, capital, margin, whitelist entries, or live configuration.

## Requirements

> **Risk and money boundary**: Grade 4 applies because passing evidence may nominate a future research canary. This feature changes research classification only. It authorizes no order, capital, margin, arming, whitelist, cap, constitution, kernel, or paid-service change. `Backtest -> Canary -> Full` remains mandatory.

### Functional Requirements

- **FR-001**: The system MUST use Cboe `PUT_History.csv` as the cash-secured S&P 500 put-writing total-return reference and Cboe `VIX_History.csv` as the option-implied volatility source.
- **FR-002**: The system MUST use Kenneth French daily market and risk-free factors for realized equity returns and FRED `DGS3MO` as the independent cash-rate cross-check.
- **FR-003**: Every source MUST record URL, first and last date, latest age, content hash, units or scale, and known methodology or basis limitation; malformed, duplicate, non-finite, non-positive index, or stale data MUST fail closed.
- **FR-004**: Daily market returns within month `t` MUST produce annualized realized variance, the final VIX close in month `t` MUST produce annualized implied variance, and their difference MUST first affect target exposure in month `t+1`.
- **FR-005**: The system MUST preregister exactly 16 candidates: four always-on PUT allocations of 25/50/75/100%; four positive variance-premium policies from 6/12-month smoothing and 50/100% maximum PUT weights; four tail-guarded policies from 6/12-month equity trend and 50/100% maximum weights; and four expanding ridge policies from 6/12-month features and 50/100% maximum weights.
- **FR-006**: Tail-guarded policies MUST require positive smoothed variance premium, positive matching-horizon equity trend, and no current VIX shock above the trailing-horizon mean plus one standard deviation.
- **FR-007**: Ridge policies MUST use fixed regularization 10, at least 60 prior labels, deterministic standardization, and only VIX level, implied-realized variance spread, equity trend, market drawdown, and prior PUT excess returns known before the target month.
- **FR-008**: Candidate returns MUST combine the chosen PUT-index allocation with cash, apply an additional annual implementation haircut of 25/50/100bp, and charge 10/25/50bp per allocation turnover; the middle 50bp annual plus 25bp turnover case is the selection and gate case.
- **FR-009**: The system MUST select exactly one candidate by highest development Sharpe after middle costs, break ties by lower 95% expected shortfall, lower drawdown, and stable candidate identity, use exactly 84 development months, embargo one month, and evaluate at least 120 untouched later months without reselection.
- **FR-010**: The standalone live lane MUST require cash-excess PSR at least 0.95, annual cash excess after middle costs at least 2%, Sharpe improvement over broad equities at least 0.05, maximum drawdown no worse than broad equities, and 95% expected shortfall no worse than broad equities.
- **FR-011**: The standalone paper lane MUST require cash-excess PSR at least 0.80, positive annual cash excess after middle costs, non-declining Sharpe versus broad equities, maximum drawdown no worse than 120% of broad equities, and 95% expected shortfall no worse than 120% of broad equities.
- **FR-012**: Non-passive candidates MUST additionally report a timing-enhancement lane against a passive PUT allocation with the same maximum weight, requiring positive annual excess, Sharpe improvement at least 0.05, non-worsening drawdown and expected shortfall, and active exposure in 10% to 90% of holdout months. This lane is diagnostic and MUST NOT veto a standalone premium pass.
- **FR-013**: The full PUT reference and a mean-zero PUT excess null MUST be evaluated under the same standalone gate, while a fixed 500-repetition 16-candidate simulation MUST report null false acceptance, planted-edge detection, and correct-selection rates.
- **FR-014**: The objective gate is passable only if synthetic null false acceptance is at most 6% and planted-edge detection is at least 80%; real PUT-reference failure MUST produce a separate `GATE_OR_REFERENCE_SUSPECT` diagnosis rather than silently lowering thresholds.
- **FR-015**: The report MUST audit prior released family decisions and classify why no prior candidate is currently adoptable, including negative economics, statistical uncertainty, post-hoc-only evidence, objective mismatch already corrected, missing clean forward evidence, or missing executable parity. It MUST NOT reclassify or promote prior candidates.
- **FR-016**: The system MUST preserve 736 prior unique audit records and append exactly 16 new unique fingerprints for 752 cumulative records.
- **FR-017**: Output MUST include every candidate and cost case, development and holdout windows, failed gates, tail metrics, model chronology, source and strategy fingerprints, real and synthetic controls, prior-adoption audit, post-hoc ranks, and live-parity blockers.
- **FR-018**: Production workflow MUST replace canonical evidence only after exact 16/16 and 752/752 completeness and uniqueness, source freshness, chronology, control, and boolean-gate checks pass.
- **FR-019**: Verdicts MUST distinguish `FACTORY_EDGE_CONFIRMED`, `PAPER_EDGE_CANDIDATE`, `REFERENCE_EDGE_CONFIRMED_SELECTION_UNCONFIRMED`, `GATE_OR_REFERENCE_SUSPECT`, and `NO_FACTORY_EDGE`.
- **FR-020**: No broker import, order path, capital or margin change, whitelist change, paid API, or result-driven candidate, threshold, feature, split, cost, or model change is permitted.
- **FR-021**: PUTW or a cash-secured SPX option overlay may be named only as intended expressions. A passing result MUST remain non-promotable until exact policy code, live history parity, tax and assignment treatment, margin and collateral rules, whitelist authorization, hardened canary, and consumer fingerprint identity exist.

### Key Entities

- **OptionsPremiumObservation**: Date, PUT index level, VIX level, market return, cash rate, assumed availability, source hash, and basis limitation.
- **VarianceRiskPremiumSnapshot**: Month, implied variance, realized variance, spread, equity trend, drawdown, VIX shock state, and target month.
- **OptionsPremiumPolicy**: Family, horizon, maximum PUT weight, model settings, cost schedule, candidate identity, and strategy fingerprint.
- **PriorAdoptionAudit**: Prior family, frozen candidate, objective route, economic and statistical classification, post-hoc status, forward evidence, and non-promotion reason.
- **OptionsPremiumDecision**: Frozen winner, standalone and timing gates, tail metrics, controls, power, prior-family audit, post-hoc ranks, and live-parity state.

## Success Criteria

### Measurable Outcomes

- **SC-001**: At least 205 aligned monthly observations remain after warm-up, leaving exactly 84 development months, one embargo month, and at least 120 untouched holdout months.
- **SC-002**: Exactly 16 current trials and 752 unique cumulative audit fingerprints are emitted reproducibly.
- **SC-003**: Every signal and training label predates its target month, and repeated identical inputs produce identical factors, weights, winner, tail metrics, gates, and fingerprints.
- **SC-004**: The latest official data produces one declared verdict without any post-result specification change.
- **SC-005**: The report answers separately whether a recognized PUT premium exists, whether timing improves it, whether the gate is passable, why prior candidates remain non-adoptable, and what live implementation evidence is missing.
- **SC-006**: Focused tests, full pytest, ruff, YAML parsing, strict harness, handoff facts, PR quality gate, production replay, deploy verification, and no-order KIS smoke complete before closure.

## Assumptions

- Cboe PUT is the best public benchmark for cash-secured monthly SPX put-writing but remains a hypothetical index, not executable fills.
- Fama-French broad-market returns are adequate for long-history equity risk comparison but are not exact SPX returns.
- The implied-realized variance difference is a direct economic signal for option insurance compensation; simple transparent timing and one fixed ridge model are enough for this bounded test.
- Expected shortfall is required because volatility selling can hide rare severe losses behind attractive average returns.
- A reference or paper pass is evidence, not permission to trade.
- The current official Cboe PUT download contains isolated older observations but a continuous daily series only from 2007-01-03. Those isolated rows are ignored so a return is never formed across a multi-year data gap.

## Risk Classification

**Grade 4 - money-path evidence classification**. No money movement is authorized by this feature.
