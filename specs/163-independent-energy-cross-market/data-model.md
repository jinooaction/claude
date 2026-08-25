# Data Model: Independent Energy Cross-Market Factory

## EnergyMarketObservation

| Field | Type | Validation |
|---|---|---|
| `series_id` | string | One of the four preregistered EIA identities |
| `period_month` | date | Unique, strictly increasing month |
| `available_month` | date | Exactly two month-starts after `period_month` |
| `value` | float | Finite and positive |
| `unit` | string | Exact expected unit for the series |
| `source_url` | string | Fixed public HTTPS URL |
| `content_digest` | string | SHA-256 digest |

## EnergyReturnObservation

| Field | Type | Validation |
|---|---|---|
| `month` | date | Unique and strictly increasing |
| `energy_factor` | float | Positive monthly total-return factor |
| `cash_factor` | float | Positive DGS3MO monthly factor |
| `incumbent_factor` | float | Positive equal-weight SPY/IEF/GLD factor |
| `source_digest` | string | SHA-256 digest of French source |

## EnergyFeatureSnapshot

| Field | Type | Validation |
|---|---|---|
| `target_month` | date | Return month being decided |
| `source_month` | date | At least two months before target month |
| `horizon_months` | integer | 6 or 12 |
| `wti_return` | float | Finite trailing return |
| `gasoline_return` | float | Finite trailing return |
| `heating_return` | float | Finite trailing return |
| `natural_gas_return` | float | Finite trailing return |
| `crack_margin` | float | 3:2:1 dollar-per-barrel proxy |
| `crack_zscore` | float | Finite expanding, past-only normalization |

## EnergyCrossMarketPolicy

| Field | Type | Validation |
|---|---|---|
| `family` | enum | `wti_trend`, `refining_margin`, `market_breadth`, `ridge_forecast` |
| `feature_horizon` | integer | 6 or 12 |
| `max_energy_weight` | decimal | 0.5 or 1.0 |
| `model_alpha` | decimal/null | 10 only for ridge; null otherwise |
| `candidate_id` | string | Deterministic from policy |
| `strategy_fingerprint` | string | Unique SHA-256 of the full decision grammar |

## EnergyCrossMarketDecision

The decision contains one immutable development winner, holdout metrics, standalone
live/paper gates, unchanged diversifier gates, empirical and synthetic controls,
all-candidate descriptive records, post-hoc ranks with promotion disabled, data/model/split/
weight fingerprints, and a live-parity block.

## State Transitions

```text
PREREGISTERED
  -> DATA_VALIDATED
  -> FAMILY_COMPLETE_16_OF_16
  -> DEVELOPMENT_WINNER_FROZEN
  -> HOLDOUT_EVALUATED
  -> FACTORY_EDGE | PAPER_CHALLENGER | NO_FACTORY_EDGE
  -> LIVE_PARITY_BLOCKED (always for spec 163 until a separate approved feature)
```

Any missing, stale, duplicated, non-finite, future-leaking, count-mismatched, or
fingerprint-mismatched evidence transitions directly to fail-closed input error and does
not replace production evidence.
