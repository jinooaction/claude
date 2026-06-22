# Data Model: Micro GTAA Live Canary

## MicroCanaryRequest

Represents the operator-controlled request file.

Fields:
- `armed`: required boolean string. `false` means preview-only; `true` allows real orders on schedule or manual dispatch.
- `capital_usd`: required integer. Must be `1..1000` for manual micro authority.
- `requested_by`: operator identifier for the forensic record.
- `stage`: expected value `micro-gtaa-live-canary`.
- `run_seq`: monotonically increasing integer for explicit retriggers.
- `warning_drawdown_pct`: warning threshold, default 3.
- `hard_stop_drawdown_pct`: hard stop target, default 5.
- `note`: free-form audit note.

Validation:
- `armed` must be exactly `true` or `false`.
- Manual `capital_usd` must not exceed 1,000.
- `hard_stop_drawdown_pct` must not exceed 5.
- `warning_drawdown_pct` must be less than `hard_stop_drawdown_pct`.

## MicroGtaaPortfolio

Represents the live micro GTAA configuration.

Fields:
- `id`: `micro-gtaa`.
- `universe`: exactly `SPYM`, `IEF`, `GLDM`.
- `weight_scheme`: `equal`.
- `top_n`: 3.
- `rebalance_mode`: `hold_replace`.
- `invested_fraction`: no more than 0.99.
- `rebalance_every_n_sessions`: 21.
- `min_notional_usd`: small enough to permit micro orders but not dust.
- `trend_filter`: SMA ensemble with windows `63`, `126`, `189`, `252`, and `on_insufficient = cash`.

Validation:
- Universe must be a subset of the whitelist.
- Whitelist must be exactly the three micro ETF symbols.
- Order types must be limit-only.
- Sessions must be regular-only.
- Caps must include per-trade, per-symbol, global exposure, canary duration, and drawdown limits.

## MicroCanaryRun

Represents one GitHub Actions execution.

Fields:
- `run_id`, `timestamp_utc`, `trigger`, `commit`.
- `armed`, `capital_usd`, `blocked`.
- `preview_json`.
- `live_result_json`.
- `measurement_log`.
- `stop_policy_summary`.

State transitions:
- `PreviewOnly`: default when `armed=false` or trigger is push.
- `Blocked`: invalid capital, invalid sentinel, or missing runtime prerequisites.
- `LiveSubmitted`: `armed=true`, trigger is schedule or manual dispatch, and all guards pass.
- `Measured`: NAV and forward verdict were recorded after preview/live attempt.

## StopPolicy

Represents the downside boundary for the experiment.

Fields:
- `warning_drawdown_pct`: default 3.
- `hard_stop_drawdown_pct`: default 5.
- `kill_switch`: existing `automation/AUTOARM_DISABLED` remains a global stop signal; the micro path also supports `armed=false` as a direct stop.

Validation:
- Stop policy is documented in sidecar output.
- Any hard-stop breach must make the next action "disarm before more real orders" visible.
