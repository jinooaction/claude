# Data Model: Independent FX Carry and Gate Power

## FxCarrySnapshot

- `as_of_date`: monthly decision date.
- `usd_spot`: USD value of one AUD, CAD, JPY, GBP, and USD after quote normalization.
- `short_rates`: annualized immediate rates for the five currencies.
- `observation_dates`: source observation used for each field.
- `spot_history`, `rate_history`, `volatility_history`: only information available by `as_of_date`.
- `complete`, `fresh`: fail-closed data flags.

## FxCarryPolicy

- `family`: `pure_carry`, `carry_momentum`, `carry_value`, or `defensive_carry`.
- `lookback_months`: 3 or 12.
- `top_n`: fixed at 2.
- `risk_lookback_months`: fixed at 12.
- `value_lookback_months`: fixed at 36.
- `max_foreign_weight`: 0.5 or 1.0.

## FxCarryCandidate

- `candidate_id`, `trial_index`, `policy`, `strategy_fingerprint`.
- `signal_series`: nine FRED series.
- `execution_symbols`: FXA, FXC, FXY, FXB, UUP.
- `instrument_basis_risk`: synthetic foreign cash differs from ETF total return.
- `live_whitelist_authorized`: always false in this feature.

## GatePowerEvidence

- `family_sizes`: 16 and 64.
- `planted_sharpes`: 0.20 through 0.80.
- `null_false_acceptance_rate`.
- `live_detection_rate`, `paper_admission_rate`, `planted_selection_rate` by Sharpe.
- `live_calibrated`: false acceptance <=5% and Sharpe 0.60 detection >=80%.

## FxCarryDecision

- `verdict`: `FACTORY_EDGE`, `PAPER_CHALLENGER`, or `NO_FACTORY_EDGE`.
- `development_selection`: one development-only winner.
- `gates`: stage, role, actual, required, pass/fail.
- `selected_candidate_id`: only for live-grade result.
- `paper_candidate_id`: only for no-capital paper result.
- `research_canary_eligible`: true only for `FACTORY_EDGE`.
- `paper_forward_eligible`: true only for `PAPER_CHALLENGER`.
- `selected_deploy_config`: null unless live-grade and separately whitelisted.

## State Transitions

`PREREGISTERED -> EVALUATED -> NO_FACTORY_EDGE | PAPER_CHALLENGER | FACTORY_EDGE`

`PAPER_CHALLENGER` may enter a separate forward-paper track but cannot transition directly to live. A
material policy change returns to `PREREGISTERED` with a new family identity.
