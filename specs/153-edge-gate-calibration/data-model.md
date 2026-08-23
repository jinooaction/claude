# Data Model: Edge Gate Calibration

## GateCalibrationScenario

- `scenario_id`: stable identifier.
- `kind`: `null` or `planted_edge`.
- `seed`, `repetitions`, `family_size`, `development_observations`, `holdout_observations`.
- `candidate_correlation`, `planted_sharpe_annual`.
- Validation: all values fixed by gate version; runtime overrides make evidence non-promotable.

## GateCalibrationReport

- `gate_version`, scenario definitions, accepted counts, acceptance rates.
- `false_acceptance_rate`, `detection_rate`, required maxima/minima.
- `passed`, `code_commit`, `timestamp_utc`.
- State: `CALIBRATED` only if both error-rate contracts pass; otherwise `CALIBRATION_FAILED`.

## StatisticalFamily

- `family_id`, `grammar_fingerprint`, `objective`, `benchmark_id`, `selection_rule`.
- `development_range`, `embargo_range`, `holdout_range`.
- `raw_trial_count`, `effective_trial_count`, candidate fingerprints.
- Validation: objective and ranges are immutable after evaluation begins.

## FamilyTrialEvidence

- candidate and strategy fingerprints.
- aligned development and holdout factor returns at each cost level.
- development segment scores and selection metrics.
- holdout confirmation and economic diagnostics.

## HierarchicalEdgeDecision

- `gate_version`, family identity, calibration state.
- global audit count, family raw count, family effective count.
- development-selected candidate ID.
- discovery DSR/PBO gates.
- holdout PSR and 50-basis-point profitability gates.
- one objective-specific economic route and non-applicable diagnostics.
- `research_canary_eligible`, selected config, safety assertions.

## State Transitions

`UNCALIBRATED -> CALIBRATED -> DISCOVERY_PASS -> HOLDOUT_CONFIRMED -> ECONOMIC_PASS -> RESEARCH_CANARY_ELIGIBLE`

Any missing or failed evidence transitions to `NO_FACTORY_EDGE`; it cannot skip stages or authorize an order.
