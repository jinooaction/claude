# Contract: Promotion Seal TOML

This contract documents the on-disk format of a promotion seal — the
artifact that binds a rule snapshot to a threshold-clearing OOS
backtest result. Implemented in `src/auto_invest/promotion/seal.py`.

A seal is the **only** mechanism by which a rule can reach `canary`
or `full-live` stage in the live worker. The worker's startup
loader refuses any rule whose `rule_snapshot_hash` does not match a
non-revoked seal (FR-P-002).

## File layout

Seals live under `data/promotions/<seal_id>.toml`. The `seal_id` is
`sha256(rule_snapshot_hash || backtest_run_id || issued_ts_utc)[:12]`.
Seals are immutable after issue. Revocation writes a new seal file
with the same `rule_snapshot_hash` and `revoked = true`; the live
worker uses the latest non-revoked seal per `rule_snapshot_hash`.

## Schema

```toml
schema_version = "002.1"

seal_id            = "abc123def456"
issued_ts_utc      = "2026-05-15T14:32:00Z"
issued_by          = "operator"          # always "operator" in v2
revoked            = false
revoked_ts_utc     = ""
revoked_reason     = ""

[rule]
path           = "config/rules/aapl_rsi.toml"
snapshot_hash  = "sha256:..."

[backtest]
run_id   = "..."
mode     = "oos"          # one of "oos" | "walkforward"
window_from_utc = "2021-01-01T00:00:00Z"
window_to_utc   = "2026-01-01T00:00:00Z"
oos_window_from_utc = "2025-07-01T00:00:00Z"
oos_window_to_utc   = "2026-01-01T00:00:00Z"

[oos_metrics]
sharpe              = "1.27"
sortino             = "1.85"
max_drawdown_pct    = "8.42"
trade_count         = 47
hit_rate            = "0.55"
avg_win_loss_ratio  = "1.31"
total_return_pct    = "14.3"
oos_window_days     = 184

[thresholds]
# Snapshot of PromotionThresholds at the time the seal was issued.
# Used to detect "thresholds changed since issue" and prompt re-issue.
min_oos_sharpe                                   = "1.0"
max_oos_drawdown_pct                             = "15"
min_oos_trade_count                              = 30
min_oos_window_days                              = 90
max_live_vs_backtest_drawdown_divergence_pct     = "5"
divergence_alert_window_days                     = 5

[verification]
# Computed at issue time; checked by `auto-invest run` at startup
# and by `auto-invest promote --check`. Any mismatch invalidates.
oos_metrics_hash    = "sha256:..."   # over the canonical [oos_metrics] table
config_hash         = "sha256:..."   # backtest run config hash
data_pin_hash       = "sha256:..."   # `as_of_ts_pin_utc` + per-instrument vendor pins
```

## Verification rules (worker startup)

When `auto-invest run` loads a rule, it MUST:

1. Compute the rule's current `snapshot_hash`.
2. Find the latest non-revoked seal with matching `rule.snapshot_hash`.
3. Re-load the referenced backtest run from
   `data/backtests/<run_id>/`.
4. Recompute `config_hash` and `data_pin_hash` from the run's
   on-disk inputs and verify they match `verification` in the seal.
5. Recompute `oos_metrics_hash` from the run's `oos/metrics.json`
   and verify it matches.
6. Verify each `[oos_metrics]` value still clears the
   `[thresholds]` snapshot.
7. If the live `PromotionThresholds` are stricter than the seal's
   snapshot, additionally verify the metrics still clear the live
   thresholds; emit a warning if not, refuse if a strict-mode flag
   is set.

Any failure rejects the rule with a logged reason. The audit log
records the rejection with the failing step number.

## Issuing a seal

`auto-invest promote --rule <path> --backtest <run_id> --issue`:

1. Load the rule, compute its snapshot hash; load the backtest run.
2. Verify the run's recorded `rule_snapshot_hash` matches.
3. Verify the run is in mode `oos` or `walkforward` and has OOS
   metrics.
4. Verify each OOS metric clears the live `PromotionThresholds`.
5. Compute `oos_metrics_hash`, `config_hash`, `data_pin_hash`.
6. Write `data/promotions/<seal_id>.toml`.
7. Insert a row into `promotion_seals`.
8. Print the `seal_id`.

## Revoking a seal

`auto-invest promote --revoke <seal_id> --reason "<text>"`:

1. Load the existing seal.
2. Write a new seal file with a new `seal_id`, the same
   `rule_snapshot_hash`, `revoked = true`, populated
   `revoked_*` fields. The original seal file is left in place
   (immutable).
3. Insert a row into `promotion_seals`.

## Live-vs-backtest divergence

The daily reporter (FR-P-004) reads each promoted rule's seal,
loads the run's `oos/metrics.json` distribution, computes the live
realised distribution from the day's audit log, and writes a row
into `divergence_events` if any tracked metric exceeds
`max_live_vs_backtest_drawdown_divergence_pct` for a single day.
After `divergence_alert_window_days` consecutive flags, the rule
is auto-halted (per-rule halt, separate from the global halt
mechanism in spec 001).
