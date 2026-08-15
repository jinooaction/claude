# Research: Broad No-Edge Vol-Target Drawdown

## Decision: Treat PSR shortfall as the primary reason to test vol targeting

**Rationale**: Current forward tracks can show strong Calmar while still failing PSR. A lower target volatility or drawdown overlay may improve confidence without inventing a new entry signal.

**Alternatives considered**: Opening live orders was rejected because money-path remains `PREVIEW_ONLY`/`NO_EDGE_YET`.

## Decision: Include live drawdown and capital ladder context

**Rationale**: The sidecars already expose rung 0, live drawdown, demote/halt budgets, and `WAIT_EDGE`. The contract must preserve why the candidate cannot be promoted directly to capital deployment.

**Alternatives considered**: Only reading forward verdicts was rejected because it would omit the live exclusion conditions the operator needs.

## Decision: End the second-wave broad no-edge chain with `wait-for-fresh-evidence`

**Rationale**: The autonomous broad no-edge second wave was cross-asset relative value, tail-risk convexity, then vol-target drawdown. After the last candidate is completed, the loop should not repeat the same candidate.

**Alternatives considered**: Pointing `next_candidate_id` back to the same candidate was rejected because it would create repeat work.
