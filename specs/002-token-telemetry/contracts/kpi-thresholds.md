# Contract: KPI Threshold Table

**File**: `config/llm_kpi_thresholds.toml`
**Loader**: `auto_invest.telemetry.thresholds`
**Status**: operator-editable; ships with conservative defaults.

## Schema

```toml
# config/llm_kpi_thresholds.toml
#
# Each KPI block declares the band entry-points for tiers C / B / A.
# A KPI's `direction` decides whether higher or lower values are better.
# Operators may edit values; KPI names and `direction` are fixed.

[cache_hit_rate]
direction = "higher_is_better"
tier_c = 0.40
tier_b = 0.70
tier_a = 0.90

[tokens_per_decision_p95]
direction = "lower_is_better"
tier_c = 8000
tier_b = 3000
tier_a = 1500

[usd_per_decision_mean]
direction = "lower_is_better"
tier_c = 0.05
tier_b = 0.01
tier_a = 0.003

[latency_p95_ms]
direction = "lower_is_better"
tier_c = 5000
tier_b = 2000
tier_a = 800
```

## Tier rules

For `direction = "higher_is_better"`:
- value ≥ `tier_a` → **A**
- value ≥ `tier_b` → **B**
- value ≥ `tier_c` → **C**
- otherwise → **N/A**

For `direction = "lower_is_better"`:
- value ≤ `tier_a` → **A**
- value ≤ `tier_b` → **B**
- value ≤ `tier_c` → **C**
- otherwise → **N/A**

A KPI computed over an empty window → tier = `"N/A"`, value = 0 (or 0.0).

## Validation

- All four KPIs MUST be present. Missing keys raise `ConfigError` at load time.
- Each block MUST have all four fields (`direction`, `tier_c`, `tier_b`, `tier_a`).
- `direction` MUST be one of `higher_is_better` / `lower_is_better`.
- For `higher_is_better`: `tier_c < tier_b < tier_a` (strictly increasing).
- For `lower_is_better`: `tier_c > tier_b > tier_a` (strictly decreasing).
- Unknown KPI keys at the top level are rejected.
