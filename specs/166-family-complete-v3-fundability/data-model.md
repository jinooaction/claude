# Data Model: Family Complete V3 and Fundability

## FactoryEvidenceAssessment

- `eligible`: all v3 checks passed.
- `contract_version`: `family-complete-v3`, `family-complete-v2-diagnostic`, or `legacy-64-diagnostic`.
- `candidate_count`, `complete_trial_count`, `global_audit_trial_count`.
- `selected_candidate_id`, `selected_strategy_fingerprint`.
- `program_multiplicity`: selected-row PSR, raw one-sided error, global trials, adjusted error,
  threshold, consumer-recomputed DSR/PBO, and producer-declared DSR/PBO.
- `checks`, `reasons`: deterministic machine-readable checks and failures.

## FundabilityAssessment

- `fundable`: all feasibility checks passed.
- `capital_usd`, `investable_usd`.
- `active_target_count`, `funded_target_count`, `funded_target_ratio`.
- `quote_coverage_ratio`.
- `target_weights`, input holdings/prices/order prices/planned orders/caps/effective side,
  `projected_quantities`, `projected_weights`.
- `l1_weight_error`, `max_leg_weight_error`.
- `checks`, `reasons`.

Serialized fundability evidence includes every deterministic input. Consumers rebuild the assessment
and require byte-equivalent JSON values before treating the preview as current evidence.

## State Transitions

- Factory v2/legacy input -> diagnostic only, never rung-1 eligible.
- Factory v3 pass + fresh exact fingerprint + hardened canary + fundability pass -> rung-1 candidate.
- Any missing/failed v3 or fundability check -> rung 0, `RESEARCH_CANARY_WAIT`.
- Existing strategy fill -> active live risk path; no new entry block on exits or demotions.
