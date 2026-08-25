# Feature Specification: USDA Crop Supply-Demand Factory

**Feature Branch**: `Codex/162-usda-crop-supply-demand`
**Created**: 2026-08-25
**Status**: Completed; grammar and gates were preregistered before any candidate result
**Input**: Test a genuinely independent crop supply-demand return source and explain whether the existing promotion standard is defective or merely conservative.

## User Scenarios & Testing

### User Story 1 - Test independent point-in-time crop information (Priority: P1)

As the operator, I can run a frozen strategy family based on USDA estimates exactly as they appeared on each release date, without later revisions leaking into earlier decisions.

**Independent Test**: The same release workbooks reproduce the same corn, wheat, soybean, and combined scarcity revisions, 16 candidate identities, and source fingerprints.

### User Story 2 - Receive an untouched-holdout decision now (Priority: P1)

As the operator, I can see whether one development-selected crop policy passes the existing live, paper, or no-edge standard on at least 120 later months.

**Independent Test**: Changing only holdout returns cannot change the development winner, and every threshold and cost remains identical before and after the result.

### User Story 3 - Distinguish a bad criterion from weak evidence (Priority: P1)

As the operator, I can see the gate's calibrated false-positive rate, detection power for this actual holdout length, and the exact failed economic or statistical gates.

**Independent Test**: The report includes the unchanged real positive/null controls, family-size calibration, holdout power, and failed-gate attribution beside the candidate verdict.

### User Story 4 - Preserve the money boundary (Priority: P1)

As the operator, I can trust that this research cannot place an order or change capital, arming, caps, the whitelist, the constitution, or the kernel.

**Independent Test**: The source has no broker/order dependency, the workflow uses no KIS secret, and incomplete or malformed evidence fails before sidecar replacement.

## Edge Cases

- Missing release months, duplicate releases, malformed workbooks, changed table labels, non-finite values, or stale latest data fail closed.
- The January 2019 government shutdown created no WASDE release; the sequence may skip that month but cannot invent a value.
- A crop marketing-year rollover is not treated as a scarcity revision; comparisons require the same projected marketing year.
- A corrected/reposted report is represented by its archived release and disclosed in source lineage.
- A statistically strong result that fails a portfolio economics gate remains ineligible.
- A passing research result still cannot trade unless an executable live implementation and exact strategy fingerprint pass the existing consumer contract.

## Requirements

> **Risk and money boundary**: Grade 4 applies because passing evidence can nominate a future research canary. This feature authorizes no order, capital, arming, whitelist, cap, constitution, kernel, or paid-service change. `Backtest -> Canary -> Full` remains mandatory.

### Functional Requirements

- **FR-001**: The system MUST discover archived USDA WASDE releases from July 2010 onward and use only the values available in each archived release.
- **FR-002**: The system MUST parse U.S. corn, wheat, and soybean projected ending stocks and total use, together with the projected marketing year and release date.
- **FR-003**: A scarcity revision MUST be the decline in ending-stocks-to-use versus one or three prior releases only when both reports refer to the same projected marketing year; otherwise it MUST be neutral.
- **FR-004**: The system MUST derive four frozen families: corn tightening, wheat tightening, soybean tightening, and synchronized crop tightening.
- **FR-005**: The system MUST generate exactly 16 candidates from four families, 1/3-release revision horizons, and 50/100% maximum inflation-hedge weights.
- **FR-006**: Candidate returns MUST use the existing point-in-time IEF bond and GLD gold proxies, hold GLD up to the policy maximum during scarcity and IEF for the remainder, and charge 10/25/50bp per turnover.
- **FR-007**: The system MUST select exactly one winner on the first 60 factor months, embargo one month, and evaluate at least 120 untouched later months without reselection.
- **FR-008**: The existing live gates MUST remain PSR at least 0.95, positive annual excess return after 50bp, incumbent correlation below 0.80, 80/20 blend Sharpe improvement at least 0.05, and non-worsening blend drawdown.
- **FR-009**: The existing paper gates MUST remain PSR at least 0.80, positive annual excess return after 50bp, correlation below 0.80, non-declining blend Sharpe, and blend drawdown no worse than 120% of incumbent.
- **FR-010**: The existing calibrated real positive control MUST pass and its null MUST fail; code-commit mismatch, failed controls, or uncalibrated evidence MUST block promotion.
- **FR-011**: The system MUST preserve 704 prior unique audit records and append exactly 16 new unique fingerprints for 720 cumulative records.
- **FR-012**: Output MUST include all gates, family calibration, holdout length and power, source URLs and hashes, split fingerprint, target-weight fingerprint, and an explicit criterion diagnosis.
- **FR-013**: Production workflow MUST publish the USDA result as the canonical strategy-factory evidence only after exact count and completeness checks pass.
- **FR-014**: No broker import, order path, capital change, whitelist change, external paid API, or result-driven threshold change is permitted.
- **FR-015**: A passing backtest MUST still expose whether an exact executable live strategy exists; research/live mismatch MUST block the capital consumer.

### Key Entities

- **WasdeRelease**: Release date, source URL/hash, crop, projected marketing year, ending stocks, total use, and stocks-to-use ratio.
- **CropRevisionSnapshot**: Release month, one/three-release same-year scarcity revisions, combined signal, completeness, and source lineage.
- **CropSupplyDemandPolicy**: Frozen family, revision horizon, maximum gold weight, candidate identity, and strategy fingerprint.
- **CropSupplyDemandDecision**: Development winner, untouched holdout metrics, calibrated power, all gates, and live-parity status.

## Success Criteria

- **SC-001**: At least 181 aligned factor months are available, leaving 60 development, one embargo, and at least 120 holdout months.
- **SC-002**: Exactly 16 current trials and 720 unique cumulative audit fingerprints are emitted reproducibly.
- **SC-003**: Repeated identical inputs produce identical winner, metrics, gates, source hashes, and target weights.
- **SC-004**: The latest official data produces a live-grade, paper, or no-edge verdict without any post-result rule change.
- **SC-005**: The report answers whether rejection comes from invalid criteria, low statistical power, weak economics, or a live implementation gap.
- **SC-006**: Focused tests, full pytest, ruff, YAML parsing, strict harness, handoff facts, PR quality gate, production replay, deploy, and no-order KIS smoke complete before closure.

## Assumptions

- USDA's archive is the point-in-time source of record for what market participants could know after each release.
- Ending-stocks-to-use revisions are a reasonable scarcity proxy, but they may not predict broad inflation or gold returns.
- IEF and GLD are already known execution exposures; this feature does not add a new symbol to the live whitelist.
- The current gate is deliberately conservative. A real positive control proves passability but does not prove every economically plausible family should pass.

## Risk Classification

**Grade 4 - money-path evidence**. No money movement is authorized by this feature.
