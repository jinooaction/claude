# Feature Specification: Full-Gate Audit and Commodity Supply-Demand Factory

**Feature Branch**: `Codex/158-full-gate-audit-commodity-supply-demand`
**Created**: 2026-08-25
**Status**: Preregistered
**Input**: Audit whether the complete promotion standard is realistically passable, then test an independent commodity supply-demand family without changing the rules after seeing holdout results.

## User Scenarios & Testing

### User Story 1 - Know whether the complete exam is valid (Priority: P1)

As the operator, I can see a real investable diversifier and its demeaned null run through the exact same five economic and statistical gates used for candidates.

**Independent Test**: AQR diversified time-series momentum after a fixed 50bp annual haircut passes the full gate against the same incumbent, while its demeaned null receives no promotion verdict.

### User Story 2 - Test a new independent return source (Priority: P1)

As the operator, I can run a frozen 16-candidate family based on official EIA petroleum supply-demand data and receive one untouched-holdout verdict.

**Independent Test**: Identical source bytes reproduce 16 identities, one development winner, one embargo month, at least 120 holdout months, and the same metrics.

### User Story 3 - Preserve the money boundary (Priority: P1)

As the operator, I can trust that a research result cannot place orders or silently change capital, arming, or the whitelist.

**Independent Test**: Missing or failed full-gate controls close promotion before any broker boundary and all selected deployment fields remain null unless every preregistered gate passes.

## Edge Cases

- Missing, stale, duplicated, non-finite, or schema-changed official series fail closed.
- A control may pass PSR while failing an economic gate; the overall full-gate control must then fail.
- A demeaned null may pass a non-return gate such as correlation; it must still fail the complete decision.
- EIA release lag removes publication lookahead but current historical files may contain revisions; the output must disclose that residual risk.
- Holdout changes must never reselect the development winner.

## Requirements

> **Risk and money boundary**: Grade 4 applies because this evidence can nominate a future live strategy. This feature authorizes no order, capital allocation, arming, whitelist, constitution, or kernel change. `Backtest -> Canary -> Full` remains mandatory.

### Functional Requirements

- **FR-001**: System MUST retain the existing Fama-French and AQR PSR controls and add a complete five-gate audit for AQR diversified time-series momentum.
- **FR-002**: The full positive control MUST use 2007-onward common months, a 50bp annual haircut, prior-known cash returns, and the exact incumbent used by commodity candidates.
- **FR-003**: The full positive control MUST require excess PSR at least 0.95, positive annual excess return, incumbent correlation below 0.80, 80/20 blend Sharpe improvement at least 0.05, and non-worsening blend maximum drawdown.
- **FR-004**: The demeaned AQR null MUST be evaluated by the same calculations and MUST not receive a full-gate pass.
- **FR-005**: Controls MUST contribute zero candidate trials, cannot be selected, and MUST block candidate promotion when missing, stale, malformed, code-mismatched, or failed.
- **FR-006**: System MUST load official EIA weekly series `WCESTUS1` commercial crude stocks, `WCRFPUS2` crude production, `WGIRIUS2` refinery gross inputs, and `WRPUPUS2` petroleum product supplied.
- **FR-007**: Every EIA observation MUST become usable only five calendar days after period end; quality output MUST disclose revision and proxy-basis risks.
- **FR-008**: System MUST derive year-over-year inventory draw, demand growth, refinery pull, and synchronized balance signals using only previously available observations.
- **FR-009**: System MUST generate exactly 16 candidates from four frozen grammars, 52/104-week normalization windows, and 50/100% maximum GSG allocations.
- **FR-010**: System MUST use GSG NAV and prior-known DGS3MO cash returns with 10/25/50bp turnover costs.
- **FR-011**: System MUST select one winner on the first 96 months, embargo one month, and evaluate at least 120 untouched holdout months without reselection.
- **FR-012**: Candidate promotion MUST retain the same diversifier gates defined in FR-003; paper admission retains PSR 0.80, positive 50bp excess, correlation below 0.80, non-declining blend Sharpe, and bounded drawdown.
- **FR-013**: System MUST preserve 688 prior records and append 16 unique fingerprints for exactly 704 global audit records.
- **FR-014**: Output MUST include every control and candidate gate, source hashes, split and target fingerprints, failed-gate attribution, and an explicit answer on whether the standard is passable.
- **FR-015**: Production workflow MUST publish the new evidence and fail closed before replacing its prior sidecar state on invalid input.
- **FR-016**: Source and tests MUST contain no broker import or order path, and live whitelist authorization MUST remain false.

### Key Entities

- **FullGateControlAudit**: Real positive and demeaned-null returns, incumbent comparison, five gates, fingerprints, and verdict.
- **SupplyDemandObservation**: EIA series, period end, availability date, value, source identity, and revision disclosure.
- **SupplyDemandPolicy**: Frozen grammar, normalization window, maximum allocation, and strategy fingerprint.
- **SupplyDemandDecision**: Development selection, untouched holdout, economic gates, audit counts, and tier verdict.

## Success Criteria

- **SC-001**: The real AQR control passes all five live gates after the frozen haircut, and the demeaned null fails the complete decision.
- **SC-002**: The report distinguishes “PSR-only valid” from “complete gate valid” and names every failing gate.
- **SC-003**: Exactly 16 new unique candidates and 704 unique global audit records are emitted.
- **SC-004**: Repeated identical inputs produce identical metrics and fingerprints; holdout-only mutations do not change the selected candidate.
- **SC-005**: Latest official data yields a deterministic live, paper, or no-edge verdict without changing thresholds after results.
- **SC-006**: Focused tests, full pytest, ruff, YAML, strict harness, handoff facts, PR gate, production replay, deploy, and KIS no-order smoke complete before closure.

## Assumptions

- A real historical positive control proves the complete gate can recognize a known strong diversifier; it does not promise future profit.
- EIA product supplied approximates demand, and petroleum signals do not perfectly match broad GSG weights.
- Current EIA history can contain revisions because vintage snapshots are unavailable in this workflow; this is reported rather than hidden.
- Thresholds, split, candidates, objective, and costs are frozen before the new holdout result is observed.

## Risk Classification

**Grade 4 - money path evidence**. No money movement is authorized by this feature.
