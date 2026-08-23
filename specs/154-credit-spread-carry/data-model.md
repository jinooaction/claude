# Data Model: Independent Credit Spread Carry

## CreditCurveSnapshot

- `as_of_date`: Decision date.
- `corporate_yields`: HQM 10-year and 20-year rates.
- `treasury_yields`: Matched 10-year and 30-year Treasury rates.
- `spreads`: Corporate minus Treasury rates.
- `history`: Point-in-time accumulated values for each signal.
- `observation_dates`, `complete`, `fresh`: Publication and safety evidence.

## CreditSpreadPolicy

- `family`: `carry_buffer`, `spread_compression`, `curve_value`, or `stress_reentry`.
- `lookback_months`: 3 or 12.
- `spread_threshold_bps`: 50 or 100.
- `confirmation_months`: 1 or 3.
- `max_credit_weight`: 0.5 or 1.0.

## CreditSpreadCandidate

- `candidate_id`, `trial_index`, `policy`, `strategy_fingerprint`.
- Signal series: HQM and Treasury curve inputs.
- Execution representatives: `LQD`, `IEF`.
- `live_expressible`: false until whitelist separately permits `LQD`.

## CreditTrialRecord

- Candidate identity, status, family.
- Development and holdout statistics at 25bp.
- Holdout total return at 50bp, turnover, and ten development segment Sharpes.

## CreditEdgeDecision

- Gate/calibration versions and exact fingerprints.
- Global audit count 640; family raw/effective count 64/[1,64].
- Development-selected candidate and diagnostics.
- Untouched holdout blend confirmation and economics.
- Eligibility, deploy text, next family, and explicit no-order safety state.

## State Transitions

`COLLECTED -> FAMILY_COMPLETE -> DEVELOPMENT_SELECTED -> HOLDOUT_CONFIRMED -> RESEARCH_ELIGIBLE`

Any missing or failed blocking evidence transitions to `NO_FACTORY_EDGE`; no state here transitions to live armed.
