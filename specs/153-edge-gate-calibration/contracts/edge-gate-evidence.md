# Contract: Hierarchical Edge Gate Evidence

Required top-level fields:

- `gate_version`, `batch_id`, `timestamp_utc`, `code_commit`
- `calibration`
- `statistical_family`
- `global_audit_trial_count`, `family_raw_trial_count`, `family_effective_trial_count`
- `development_selection`, `holdout_confirmation`, `economic_route`
- `decision`, `safety`

`decision` must contain:

- `verdict`: `FACTORY_EDGE` or `NO_FACTORY_EDGE`
- `selected_candidate_id`: non-null only when every applicable gate passes
- `provisional_best_candidate_id`
- `objective`: `replacement` or `diversifier`
- `gates`: every gate with `gate_id`, `passed`, `actual`, `required`, `stage`, and `blocking`
- `research_canary_eligible`
- `selected_strategy_fingerprint` and `selected_deploy_config`

Fail-closed rules:

- Legacy or missing `gate_version` cannot be treated as revised evidence.
- Calibration failure makes `research_canary_eligible=false`.
- PBO row count must equal `family_raw_trial_count`; global audit rows are forbidden in PBO.
- Holdout candidate ID must equal the development-selected candidate ID.
- Only the preregistered objective route is applicable; changing it requires a new family fingerprint.
- This contract authorizes no broker call, capital allocation, whitelist change, or live arming.
