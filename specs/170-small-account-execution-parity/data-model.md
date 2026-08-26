# Data Model: Small-Account Execution Parity

## Complete Canary Window

- `symbols`: exact signal universe
- `sessions`: latest ordered intersection of every symbol's stored session dates
- `date_start`, `date_end`: inclusive replay bounds
- `audit_integrity_holes`: real `(symbol, XNYS session)` holes inside those bounds

## Execution Proxy Pair Evidence

- `signal_symbol`, `execution_symbol`
- `common_sessions`, `first_session`, `last_session`
- `return_correlation`
- `annualized_tracking_error`
- `annualized_return_gap`
- `median_execution_dollar_volume_usd`
- `checks`: independently recomputable threshold results

## Execution Proxy Parity Evidence

- `schema_version`
- `observed_at_utc`
- `contract`: frozen threshold values
- `symbol_map`: signal-to-execution mapping
- `pairs`: one evidence row per exact mapping pair
- `passed`: true only when every required pair and check passes
- `evidence_digest`: canonical SHA-256 over all evidence fields except itself

## Entry Execution Readiness

- `fundability_passed`: exact current-capital whole-share preview result
- `execution_proxy_parity_passed`: validated fresh parity result for the live map
- `entry_execution_ready`: logical AND of the two values

