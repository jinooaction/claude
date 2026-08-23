# Data Model: Independent Treasury Carry Factory

## TreasuryCurvePoint

| Field | Type | Rule |
|---|---|---|
| `series_id` | string | One of DGS3MO, DGS2, DGS5, DGS10, DGS30 |
| `maturity_years` | decimal | 0.25, 2, 5, 10, or 30 |
| `observation_date` | ISO date | Original official observation date |
| `available_date` | ISO date | Must be no later than decision date |
| `yield_pct` | decimal or null | Null remains missing; no forward fill across months |
| `source` | string | Official source identifier |

## TreasuryCurveSnapshot

| Field | Type | Rule |
|---|---|---|
| `as_of_date` | ISO date | Decision evidence time |
| `yields` | map | Maturity symbol to latest known yield |
| `history` | map of arrays | Values end at or before `as_of_date` |
| `complete` | boolean | All five latest values present |
| `fresh` | boolean | Latest production values within seven days |
| `publication_safe` | boolean | Every available date <= as-of date |
| `data_fingerprint` | sha256 string | Canonical source and values digest |

## TreasuryCarryPolicy

| Field | Allowed values |
|---|---|
| `family` | `carry_roll`, `carry_rate_trend`, `defensive_curve`, `curve_barbell` |
| `max_maturity_years` | 10, 30 |
| `lookback_months` | 3, 12 |
| `top_n` | 1, 2 |
| `signal_strength` | 0.5, 1.0 |

Four times two times two times two times two gives exactly 64 policies. Every field changes the
target-weight rule and is part of the policy fingerprint.

## TreasuryCarryCandidate

| Field | Rule |
|---|---|
| `candidate_id` | Stable family plus digest identifier |
| `trial_index` | 1 through 64 |
| `policy` | One frozen TreasuryCarryPolicy |
| `strategy_fingerprint` | Digest of execution-relevant portfolio configuration |
| `signal_symbols` | DGS maturity series |
| `execution_symbols` | SGOV, SHY, IEI, IEF, TLT mapping |
| `deploy_config_text` | Present for every live-expressible policy, selected only on full pass |

## TreasuryTrialRecord

| Field | Rule |
|---|---|
| `status` | `complete` only after all months and costs finish |
| `sharpe_25bps` | Ranking metric |
| `cagr_25bps` | Same holdout dates as benchmark |
| `max_drawdown_25bps` | Positive percentage magnitude |
| `calmar_25bps` | Null only when undefined |
| `total_return_50bps` | Must be positive for promotion |
| `turnover` | Sum of absolute monthly weight changes |
| `segment_sharpes` | Exactly ten chronological values |
| `segment_wins` | Candidate segment Sharpe above Treasury ladder |

## TreasuryFactoryDecision

State transition:

`INPUT_BLOCKED -> NO_FACTORY_EDGE` when data or prior evidence fails.
`EVALUATED -> NO_FACTORY_EDGE` when any gate fails.
`EVALUATED -> FACTORY_EDGE` only when every gate passes.

`FACTORY_EDGE` carries exactly one selected candidate and deploy config. `NO_FACTORY_EDGE` carries
neither and names the next independent strategy family.

## LiveTreasuryEvidence

The order planner accepts evidence only when candidate ID, strategy fingerprint, data fingerprint,
code commit, freshness, full-gate verdict, and target-weight digest match the configured policy.
