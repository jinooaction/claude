# Research: Research Canary Evidence Parity

## Confirmed production defect

- The latest strategy factory sidecar reports a preregistered current family of 16 candidates, 16 complete trials, and 704 unique cumulative audit fingerprints.
- The capital workflow, ladder CLI, and first-entry revalidation still require exactly 64 candidates and 64 complete trials.
- Therefore a current `gate_version=2.0` family can publish a valid `FACTORY_EDGE` and still be rejected before assignment, at the ladder, and before the first order.
- The current supply-demand family is not a winner: holdout excess PSR is 0.705637, below 0.95. Fixing the contract must not promote it.

## Decision 1 - Validate completeness, not a stale family size

**Decision**: For `gate_version=2.0`, require at least 16 preregistered candidates, `complete_trial_count == candidate_count`, the four required audit gates (`complete_family_trials`, `prior_audit_complete`, `global_audit_trials`, `unique_audit_fingerprints`), matching audit counts, and every blocking gate to pass.

**Rationale**: Candidate count is a property of a preregistered family grammar. Statistical correction must use all trials actually registered for that family; forcing an unrelated legacy size neither lowers false positives nor proves completeness.

**Alternatives considered**:

- Keep 64 forever: rejected because current production families intentionally register 16 and can never satisfy the consumer.
- Pad every family to 64 near-duplicate candidates: rejected because duplicate variants increase multiplicity penalties without adding independent economic hypotheses.
- Trust `research_canary_eligible` alone: rejected because malformed or contradictory evidence would bypass independent consumption checks.

## Decision 2 - One shared consumer contract

**Decision**: Put the factory evidence completeness check in one pure module and reuse it in zero-capital assignment, ladder evaluation, and live-entry revalidation.

**Rationale**: Three hand-written contracts caused the current drift. One decision object makes the same missing field fail in every money-path stage.

**Alternatives considered**:

- Update only the two Python consumers: rejected because workflow assignment would still refuse the winner.
- Update only the workflow: rejected because the first live entry would still fail closed after arming.

## Decision 3 - Preserve statistical and capital thresholds

**Decision**: Keep producer-owned preregistered blocking gates unchanged and require all of them. Keep the 10% research cap, 20% exploration contract, and higher-rung live gates unchanged.

**Rationale**: The defect is contract shape, not evidence strength. Dynamic family size is safe only when the producer proves full completion, cumulative audit preservation, selected configuration, and all blocking gates.

## Decision 4 - Amend constitution X.4 explicitly

**Decision**: Replace “exactly 64” with a versioned completeness contract: at least 16, all preregistered candidates complete, the four required audit gates and their counts agree, all blocking gates pass, evidence is fresh, hardening passes, and fingerprints match.

**Rationale**: The current implementation and constitution disagree. A hidden implementation workaround would violate the repository safety perimeter.

## Rollback

Revert the shared validator, its three consumers, workflow wording, and constitution amendment together. Do not delete sidecars, trial ledgers, or audit catalogs.
