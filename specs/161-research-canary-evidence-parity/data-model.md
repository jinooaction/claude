# Data Model: Research Canary Evidence Parity

## FactoryEvidenceAssessment

- `eligible`: whether the factory evidence contract is complete before freshness, hardening, and live fingerprint checks
- `contract_version`: legacy-64 or family-complete-v2
- `candidate_count`, `complete_trial_count`
- `selected_candidate_id`, `selected_strategy_fingerprint`
- `checks`: named booleans for counts, verdict, required audit gates, blocking gates, and selected output
- `reasons`: failed check names in deterministic order

## RequiredAuditGate

- `gate_id`: `complete_family_trials`, `prior_audit_complete`, `global_audit_trials`, or `unique_audit_fingerprints`
- `passed`: must be true
- `actual`, `required`: must parse as equal non-negative integers for the four required audit gates
- `blocking`: omitted means blocking; explicit false is diagnostic only

## FactoryResearchCanaryEvidence

- shared `FactoryEvidenceAssessment`
- evidence age and maximum age
- hardened canary verdict
- selected config parse result
- selected, validated, and live strategy fingerprints
- final state: `RESEARCH_CANARY_READY` or `RESEARCH_CANARY_WAIT`

## State Transitions

- incomplete or contradictory evidence -> WAIT at rung 0
- complete factory contract + fresh hardening + exact fingerprint -> rung 0 to rung 1 (10%)
- rung 1 without later live evidence -> STAY at rung 1
- first fill still zero and latest eligibility disappears -> rung 1 to rung 0
- rung 2 and above -> unchanged existing forward/live transitions
