# Contract: Operator Rules Configuration (TOML)

The operator authors a single TOML file (default path
`config/rules.toml`) that declares the whitelist, sizing caps, and
trading rules. The worker loads this file at startup, validates it, and
freezes the resulting structures (FR-001, FR-015).

## File layout

```toml
# config/rules.toml — operator-authored, version-controlled.

[caps]
per_trade_pct = 5.0
per_symbol_pct = 20.0
global_exposure_pct = 80.0
canary_capital_pct = 5.0
canary_min_duration_days = 10
canary_acceptance_drawdown_pct = 3.0

[whitelist]
symbols = ["AAPL", "MSFT", "SPY"]
accounts = ["${KIS_ACCOUNT_NO}"]    # "${...}" expands from .env at load
order_types = ["LIMIT"]              # MARKET requires explicit opt-in below
sessions = ["REGULAR"]

[[rules]]
id            = "spy-morning-dip"
symbol        = "SPY"
stage         = "CANARY"
priority      = 10
enabled       = true

  [rules.trigger]
  kind        = "price"               # one of: time / price / indicator
  direction   = "<="                  # only for kind = "price"
  threshold   = 540.00                # USD
  cooldown_seconds = 600

  [rules.action]
  side        = "BUY"
  order_type  = "LIMIT"
  qty         = 5
  limit_price = "trigger - 0.10"      # USD; relative formula allowed for limit orders

[[rules]]
id            = "msft-ema-cross"
symbol        = "MSFT"
stage         = "CANARY"
priority      = 20
enabled       = true

  [rules.trigger]
  kind        = "indicator"
  indicator   = "EMA_CROSS"
  timeframe   = "1d"
  cooldown_seconds = 86400

    [rules.trigger.params]
    fast_period = 20
    slow_period = 50
    direction   = "fast_above_slow"

  [rules.action]
  side        = "BUY"
  order_type  = "LIMIT"
  qty         = 3
  limit_price = "last_close * 1.001"
```

## Validation contract (enforced by `config/loader.py`)

| Rule | Enforced behavior on violation |
|------|-------------------------------|
| All `[whitelist].symbols` are uppercase A-Z 0-9 only | refuse to start, exit code 2 |
| Every `rules[*].symbol` appears in `[whitelist].symbols` | refuse to start, exit code 2 |
| `caps.per_trade_pct ≤ caps.per_symbol_pct ≤ caps.global_exposure_pct` | refuse to start, exit code 2 |
| `caps.canary_capital_pct ≤ caps.per_symbol_pct` | refuse to start, exit code 2 |
| `rules[*].id` values are unique | refuse to start, exit code 2 |
| `rules[*].action.order_type` ∈ `whitelist.order_types` | refuse to start, exit code 2 |
| `rules[*].trigger.kind` ∈ {`time`,`price`,`indicator`} | refuse to start, exit code 2 |
| Any `${VAR}` expansion references an undefined env var | refuse to start, exit code 2 |
| File modified while worker is running | live edits ignored; new values take effect only after restart (FR-015) |

## Reload semantics

`SIGHUP` and file-watch are NOT supported in v1. Operators rerun
`auto-invest run` after editing the file. The previous worker process
must be stopped first; the persistent halt flag remains effective
across the gap if it was set.

## Versioning

The file has no schema version field in v1. A future schema change will
add `[meta] schema_version = "X"` and the loader will refuse files
without an explicit version once that field exists.
