# Contract: Supply-Demand Factory Evidence

- `schema_version`: `1.0`
- `gate_version`: current edge gate version
- `full_gate_controls.verdict`: `FULL_GATE_CONTROLS_VALID` only when the real positive passes and the demeaned null does not
- `candidate_count`: exactly `16`
- `prior_trial_count`: exactly `688`
- `global_audit_trial_count`: exactly `704`, all unique
- `development_selection.months`: `96`
- `holdout_confirmation.embargo_months`: `1`
- `holdout_confirmation.months`: at least `120`
- `decision.objective`: `commodity_fundamental_supply_demand_diversifier`
- `decision.verdict`: `FACTORY_EDGE`, `PAPER_CHALLENGER`, or `NO_FACTORY_EDGE`
- `decision.gates`: every full-gate actual, requirement, stage, and pass state
- `decision.selected_deploy_config`: null unless all live gates pass
- `decision.live_whitelist_authorized`: always false in this feature
- `safety`: no broker API, no orders, no capital/arming/whitelist/constitution/kernel change
