# Data Model: Calibrated Research Entry

## ResearchFamilyAuditRow

- `research_family_id`: deterministic family identifier derived from immutable audit identity fields
- `candidate_count`: number of raw candidate rows in the family
- `candidate_identity_digest`: SHA-256 of sorted `candidate_id|strategy_fingerprint` pairs
- `status_counts`: complete/rejected status counts

## CalibratedResearchEntry

- `method`: `calibrated-family-risk-budget-v1`
- `selected_holdout_psr`: selected raw row PSR
- `required_holdout_psr`: 0.95
- `recomputed_pbo`: current-family PBO
- `maximum_pbo`: 0.25
- `recomputed_dsr`: integrity-checked diagnostic
- `diagnostic_dsr_threshold`: 0.95
- `family_count`: independently reconstructed family count
- `per_family_false_acceptance_max`: 0.01
- `program_false_acceptance_budget`: 0.20
- `program_false_acceptance_bound`: family count multiplied by per-family maximum

## RawMultiplicityDiagnostic

- `global_trial_count`: raw cumulative candidate count
- `required_psr`: raw Bonferroni diagnostic requirement
- `adjusted_p`: raw Bonferroni diagnostic value
- `blocking`: always false under gate v3.1

## Invariants

1. Every audit row maps to exactly one known family.
2. Claimed and recomputed family IDs and summaries are identical.
3. The selected candidate is the consumer-recomputed development winner and remains the exact audit-tail row.
4. Current family remains the exact audit tail.
5. Calibration code commit matches the strategy factory code commit.
6. Missing calibration, raw rows, family summary, PSR, PBO, DSR, or parity fails closed.
