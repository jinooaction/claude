# Contract: Versioned Factory Evidence Completeness

## Legacy contract

Evidence without `gate_version=2.0` remains compatible only when:

- `candidate_count == 64`
- `complete_trial_count == 64`
- `decision.verdict == FACTORY_EDGE`
- `decision.research_canary_eligible == true`
- every supplied gate passes
- selected candidate, config, and strategy fingerprint are present

## Family-complete v2 contract

Evidence with `gate_version=2.0` is complete only when:

- `candidate_count >= 16`
- `complete_trial_count == candidate_count`
- `complete_family_trials`, `prior_audit_complete`, `global_audit_trials`, and `unique_audit_fingerprints` exist and pass
- each required audit gate reports equal `actual` and `required` counts
- the global audit trial count equals the unique strategy fingerprint count
- every gate except explicit `blocking=false` diagnostics passes
- `decision.verdict == FACTORY_EDGE`
- `decision.research_canary_eligible == true`
- selected candidate, config, and strategy fingerprint are present

## Operational gates

Completeness alone cannot move capital. The consumer also requires:

- evidence age from 0 through 36 hours
- hardened canary `PASS`
- selected config parses as a live portfolio
- selected config fingerprint equals evidence fingerprint
- live portfolio fingerprint equals selected fingerprint
- account NAV and all existing order safety gates remain valid

## Capital boundary

- This contract can authorize only rung 1 at 10% of account NAV.
- Rung 2 and higher retain their existing forward and live evidence gates.
- Any missing or contradictory field fails closed.
