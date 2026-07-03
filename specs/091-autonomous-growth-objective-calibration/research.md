# Research: Autonomous Growth Objective Calibration

## Decision 1: Report the objective function before changing ranking behavior

**Decision**: Add the objective calibration contract to the autonomous-work report while preserving the existing deterministic ranking order.

**Rationale**: The current ranking already enforces repair priority, released-work consumption, macro growth progression, and operator-approval gates. Changing ranking in the same step would make it harder to distinguish "better observability" from "different work selection." Reporting the purpose function first gives the next session a measurable baseline and safe rollback point.

**Alternatives considered**:

- Replace `_packet_sort_key()` with a new weighted score immediately. Rejected because it could reorder safety or liveness repairs without enough historical calibration.
- Keep the candidate template text only. Rejected because the user asked for measurable objective, exploration budget, stop conditions, and learning metrics.

## Decision 2: Use deterministic 0-100 component scores

**Decision**: Score each candidate on five visible components: growth leverage, evidence readiness, validation cost fit, safety margin, and learning value. Keep each component in a 0-100 range and publish a weighted total.

**Rationale**: Component scores are easy to inspect, stable in tests, and sufficient to explain why a candidate is attractive or risky. A normalized range avoids tying this contract to current `priority_score` magnitudes.

**Alternatives considered**:

- Use raw priority score only. Rejected because it hides evidence readiness and safety tradeoffs.
- Use floating-point optimization. Rejected because deterministic report output and Markdown readability matter more than mathematical precision here.

## Decision 3: Treat exploration budget as Codex work-scope discipline

**Decision**: Publish exploration budget fields for max ranked candidates, max parallel candidates, validation time, and required closure gates. These are not trading budgets.

**Rationale**: The autonomous growth loop's immediate risk is repeated half-finished work or unbounded candidate hopping. The budget should guide Codex execution and handoff behavior, not capital allocation.

**Alternatives considered**:

- Reuse trading drawdown or capital budgets. Rejected because this feature must not touch money path or safety perimeter.
- Omit budget fields from JSON and keep them only in docs. Rejected because sidecar consumers need a machine-readable contract.

## Decision 4: Close the candidate through released-work after implementation

**Decision**: Add `completed_candidate_id: candidate-autonomous-growth-objective-calibration` in this spec's contract once the tasks are complete.

**Rationale**: This follows spec 079's completion ledger and prevents the same macro candidate from being reselected after release.

**Alternatives considered**:

- Suppress the candidate by hard-coded ID. Rejected because released-work is the established reusable completion mechanism.
- Leave the candidate open for observation. Rejected because the implementation itself is the objective calibration contract.
