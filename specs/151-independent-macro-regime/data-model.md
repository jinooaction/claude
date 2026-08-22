# Data Model: 독립 거시 레짐 전략군

## MacroSnapshot

- `as_of_date`, `generated_at_utc`, `source_commit`
- `yield_spread_10y2y`, `curve_state`, `inversion_days`, `resteepening_state`
- `cpi_yoy`, `cpi_direction_3m`, `cpi_direction_6m`, `cpi_available_date`
- `sahm_realtime`, `sahm_direction_3m`, `sahm_direction_6m`, `sahm_available_date`
- `vix_close`, `vix_band`, `vix_confirmation_days`, `vix_cooldown_days`
- `source_freshness`, `cross_check_status`, `complete`

## MacroPolicyCandidate

- `candidate_id`, `trial_index`, `family`, `base_portfolio`
- `thresholds`, `confirmation_period`, `cooldown_period`, `tilt_pct`
- `strategy_fingerprint`, `deploy_config_text`
- `live_expressible`, `blocked_reason`

`base_portfolio`는 `equal_3asset` 또는
`factory-relative_momentum-cb2e32f74390`만 허용한다.

## ExploratoryTrialReplay

- `exploration_batch_id`, `candidate_id`, `grammar_version`
- `status=EXPLORATORY_REJECTED`
- 비용별 성과, 10개 구간 샤프, 전략 지문
- `observed_during_design=true`

## MacroTrialRecord

- 기존 `TrialRecord` 필드
- `macro_data_fingerprint`, `snapshot_start`, `snapshot_end`
- `research_live_parity_digest`
- `data_quality_gates`

## MacroFactoryDecision

- 기존 `FactoryDecision` 필드
- `production_trial_count=256`
- `exploratory_trial_count=192`
- `current_trial_count=64`
- `multiplicity_trial_count=512`
- `vintage_integrity`, `research_live_parity`, `macro_data_freshness`

## LiveMacroEvidence

- `source_commit`, `generated_at_utc`, `latest_observation_utc`
- `candidate_id`, `strategy_fingerprint`, `policy_digest`
- `snapshot_digest`, `target_weights_digest`
- `fresh`, `complete`, `cross_checked`

## State Transitions

- data missing/stale/invalid -> factory failed, no winner
- 192 replay missing -> factory failed, no winner
- 64 complete + all existing and macro gates PASS -> FACTORY_EDGE
- FACTORY_EDGE + live parity + existing operational gates PASS -> existing rung 1 review
- any mismatch -> rung 0 remains
