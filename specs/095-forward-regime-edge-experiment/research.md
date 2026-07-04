# Research: Forward Regime Edge Experiment

## Decision: Materialize the work packet as a report/probe, not as a live workflow

**Rationale**: The selected candidate asks for a no-live experiment contract and validation criteria. A report/probe can consume the same sidecars as the work packet, leave a reproducible artifact, and avoid broker, capital, or live-strategy effects.

**Alternatives considered**:

- Add a scheduled workflow immediately. Rejected because the candidate is contract design; scheduling can follow once the contract proves useful.
- Only add SDD documents. Rejected because the next session would still need to reassemble sidecars manually.

## Decision: Treat current forward insufficiency as observation wait

**Rationale**: The latest forward tournament has tracks below the minimum comparable observation count. The correct answer is not "edge" or "no edge"; it is a stable contract plus a wait gate that says what evidence must mature.

**Alternatives considered**:

- Rank by temporary drawdown or return. Rejected because premature metrics are explicitly noise in the existing forward tournament module.
- Block the contract until all tracks are comparable. Rejected because the contract itself can be built now and is useful for future monitoring.

## Decision: Keep regime analysis as a gate and context, not a new trading signal

**Rationale**: Existing sidecars already expose regime context and track behavior. This feature should define how regime brittleness will be reviewed, while deeper per-regime NAV attribution remains a future experiment.

**Alternatives considered**:

- Wire new regime-stratify input as a hard dependency. Rejected because the selected work packet names five required inputs; adding a sixth hard dependency would change the contract before the first report exists.

## Decision: Completion marker closes only this contract candidate

**Rationale**: This spec completes `candidate-forward-regime-edge-experiment`, not the broader investment-edge frontier. Closing this candidate should let the existing investment-edge map advance to `candidate-signal-diversification-edge-experiment`.

**Alternatives considered**:

- Close all investment-edge candidates. Rejected because signal diversification and cost-adjusted edge experiments are separate work.
