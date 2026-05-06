# Contract: Backtest Run TOML

This contract documents the canonical TOML shape for a backtest run.
Implemented in `src/auto_invest/config/backtest.py` (Pydantic v2).

Every backtest run has a TOML form, even ones launched with CLI
flags — the engine generates `data/backtests/<run_id>/inputs/run.toml`
before starting the run, so the run is always reproducible from its
own directory.

A run is uniquely identified by the SHA-256 hash of the
canonicalised TOML *plus* the rule snapshot hash *plus* the data
pin hash. Two runs with identical inputs produce the same `run_id`.

## Schema

```toml
# data/backtests/<run_id>/inputs/run.toml
schema_version = "002.1"

[rule]
# Either `path` (TOML rule from spec 001) or `module` (Python module
# exposing a `Strategy` symbol). Exactly one is required.
path = "config/rules/aapl_rsi.toml"
# module = "myproject.strategies.aapl_rsi:Strategy"
snapshot_hash = "sha256:..."   # validated against the on-disk rule

[window]
from_utc = "2021-01-01T00:00:00Z"
to_utc   = "2025-12-31T00:00:00Z"
as_of_ts_pin_utc = "2026-05-06T00:00:00Z"   # point-in-time barrier

[[instruments]]
asset_class = "equity"
venue       = "nasdaq"
symbol      = "AAPL"
vendor      = "kis"   # overrides config/data.toml default

# A run may declare more than one instrument:
# [[instruments]]
# asset_class = "crypto"
# venue       = "binance"
# symbol      = "BTC-USD"
# vendor      = "crypto_public"

[mode]
kind = "oos"   # one of "single" | "walkforward" | "oos"

# Required when mode.kind = "oos"
[mode.oos]
from_utc = "2025-07-01T00:00:00Z"
to_utc   = "2026-01-01T00:00:00Z"

# Required when mode.kind = "walkforward"
# [mode.walkforward]
# train_window_days = 365
# test_window_days  = 90
# step_days         = 90
# min_folds         = 4

[cost_model]
commission_bps         = "0"
commission_min_usd     = "0"
half_spread_bps        = "5"
impact_coeff           = "0.1"
participation_cap_pct  = "10"

# Optional per-symbol overrides. Any field not listed inherits from
# the parent [cost_model] block.
[cost_model.per_symbol_overrides.AAPL]
half_spread_bps = "3"

[runtime]
seed                  = 0
max_runtime_seconds   = 600
```

## Validation rules

- `schema_version` MUST match the engine's supported list. Mismatch
  is a hard error at load time.
- `window.from_utc < window.to_utc`, both UTC, both ≤
  `as_of_ts_pin_utc`.
- `as_of_ts_pin_utc` MUST be ≤ the current wall clock at run time.
  A pin in the future is rejected (no time travel).
- Each `[[instruments]]` triple `(asset_class, venue, symbol)` MUST
  appear in the `Whitelist` from spec 001. The whitelist is
  authoritative; an instrument missing from the whitelist is
  rejected even for backtest.
- `vendor` (when set) MUST be a registered ingestion adapter for
  the instrument's `(asset_class, kind)` pair.
- Exactly one of `[mode.oos]` / `[mode.walkforward]` is present
  according to `mode.kind`.
- Decimal fields are quoted strings; the loader rejects float
  literals to avoid binary precision drift.
- `cost_model.commission_bps`, `half_spread_bps`,
  `participation_cap_pct` ≥ 0; `impact_coeff` ≥ 0.

## Hash canonicalisation

The `config_hash` is computed by:

1. Loading the TOML.
2. Sorting all keys lexicographically.
3. Normalising decimal strings (strip trailing zeros, no scientific
   notation).
4. Re-emitting as canonical TOML.
5. SHA-256 of the canonical bytes.

Two TOML files that differ only in whitespace, key order, or
decimal formatting MUST produce the same `config_hash`. This is
verified by a property-based test in `tests/unit/backtest/test_config_hash.py`.
