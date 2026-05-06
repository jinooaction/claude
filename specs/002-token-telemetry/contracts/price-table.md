# Contract: Anthropic Model Price Table

**File**: `config/llm_prices.toml`
**Loader**: `auto_invest.telemetry.prices`
**Status**: operator-editable; ships with public-pricing defaults as of 2026-05-06.

## Schema

```toml
# config/llm_prices.toml
#
# Per-million-token USD prices. Cache-read is typically ~0.1× input;
# cache-write is typically ~1.25× input (Anthropic pricing convention).
# Operators MUST update this file when Anthropic publishes price changes.

[claude-opus-4-7]
usd_per_million_input_tokens         = 15.0
usd_per_million_output_tokens        = 75.0
usd_per_million_cache_read_tokens    = 1.5
usd_per_million_cache_write_tokens   = 18.75

[claude-sonnet-4-6]
usd_per_million_input_tokens         = 3.0
usd_per_million_output_tokens        = 15.0
usd_per_million_cache_read_tokens    = 0.3
usd_per_million_cache_write_tokens   = 3.75

[claude-haiku-4-5-20251001]
usd_per_million_input_tokens         = 1.0
usd_per_million_output_tokens        = 5.0
usd_per_million_cache_read_tokens    = 0.1
usd_per_million_cache_write_tokens   = 1.25
```

## Cost computation

For a metered call against `model`:

```
cost_usd =
    input_tokens        × table[model].usd_per_million_input_tokens        / 1_000_000
  + output_tokens       × table[model].usd_per_million_output_tokens       / 1_000_000
  + cache_read_tokens   × table[model].usd_per_million_cache_read_tokens   / 1_000_000
  + cache_write_tokens  × table[model].usd_per_million_cache_write_tokens  / 1_000_000
```

All arithmetic uses `Decimal`; the result is rounded to 6 decimal places (sub-cent precision is preserved for KPI aggregation).

## Failure modes

- **Model not in table**: `compute_cost` returns `None`. The meter persists `cost_usd = NULL` and writes a `DATA_QUALITY_ISSUE` audit row with `issue = "unknown_model_in_price_table"`.
- **File missing or invalid**: startup error mirroring FR-011 — exit 2.
- **Negative price**: rejected at load time.

## Validation

- Every block MUST have all four fields (`usd_per_million_input_tokens`, `usd_per_million_output_tokens`, `usd_per_million_cache_read_tokens`, `usd_per_million_cache_write_tokens`).
- All values MUST be `>= 0`.
- Model names are free-form strings; they are matched verbatim against the `model` field of the Anthropic response.
- Loader records a `PRICE_TABLE_LOADED` audit event with the file's SHA-256 so cost-history is reproducible.
