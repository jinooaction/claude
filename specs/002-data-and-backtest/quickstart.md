# Quickstart: Backtest Engine & Multi-Asset Data

This guide walks the operator through the first end-to-end use of
spec 002: ingest a year of historical data for one symbol, run a
backtest of a candidate rule, evaluate the OOS metrics, and issue a
promotion seal.

> **Constitution recap**: principle VI (`backtest → canary →
> full-live`) becomes machinery in spec 002. After this guide is
> complete, the live worker (spec 001's `auto-invest run`) will
> accept the rule for canary; before this guide is complete, it
> will not.

## Prerequisites

- Spec 001 quickstart already completed: working `uv` venv, working
  `.env` with KIS credentials, `data/auto_invest.db` migrated.
- `db migrate` must be re-run after pulling spec 002 to add the new
  tables:

```bash
uv run auto-invest db migrate
```

## 1. Configure data sources

Create `config/data.toml`:

```toml
schema_version = "002.1"

# Adapters that this worker is allowed to use. Deny-by-default.
enabled_adapters = ["kis_us_equity", "crypto_public"]

# Per-(asset_class, kind) default vendor for the backtest reader.
[default_vendor_per_kind]
"equity:ohlcv_1d" = "kis"
"equity:ohlcv_1m" = "kis"
"crypto:ohlcv_1h" = "crypto_public"
"crypto:ohlcv_1d" = "crypto_public"

# Bars from two vendors that disagree by more than this fraction
# raise a `vendor_disagreement` data-quality event.
vendor_disagreement_tolerance_bps = "10"
```

## 2. Ingest historical data

Pull two years of daily bars for AAPL from the KIS adapter:

```bash
uv run auto-invest data ingest \
    --adapter kis_us_equity \
    --instrument equity:nasdaq:AAPL \
    --kind ohlcv_1d \
    --from 2023-01-01 \
    --to 2025-12-31
```

Verify the store:

```bash
uv run auto-invest data describe --symbol AAPL --kind ohlcv_1d
```

Expected output (truncated):

```
asset_class venue   symbol kind        vendor earliest         latest           gaps revisions
equity      nasdaq  AAPL   ohlcv_1d    kis    2023-01-03T...   2025-12-30T...   0    0
```

Optional: ingest a year of BTC-USD daily bars from the crypto adapter
to exercise the always-open calendar path:

```bash
uv run auto-invest data ingest \
    --adapter crypto_public \
    --instrument crypto:binance:BTC-USD \
    --kind ohlcv_1d \
    --from 2024-01-01 \
    --to 2025-12-31
```

## 3. Author a candidate rule (or reuse one from spec 001)

For this walkthrough we use a minimal RSI-below rule on AAPL:

`config/rules/aapl_rsi_demo.toml` (already in the spec 001 shape;
no syntax changes in 002):

```toml
id = "aapl_rsi_below_30"
symbol = "AAPL"
stage = "BACKTEST"
priority = 100
enabled = true

[trigger]
kind = "indicator"
indicator = "RSI_BELOW"
params = { period = 14, threshold = "30" }
timeframe = "1d"
cooldown_seconds = 86400

[action]
side = "BUY"
order_type = "LIMIT"
quantity = 1
limit_price_formula = "last_close * 0.999"
```

## 4. Run a backtest with held-out OOS

```bash
uv run auto-invest backtest \
    --rule config/rules/aapl_rsi_demo.toml \
    --from 2023-01-01 \
    --to 2025-12-31 \
    --mode oos \
    --oos-from 2025-07-01 \
    --oos-to 2025-12-31
```

The engine:

1. Generates `data/backtests/<run_id>/inputs/run.toml`.
2. Streams bars from `historical_bars`, blocks any read with
   `as_of_ts > as_of_ts_pin_utc` or content-ts past the strategy's
   decision time.
3. Applies the spec 001 risk gates against simulated orders.
4. Simulates fills with the default cost model
   (5 bps half-spread + sqrt impact, 10% participation cap).
5. Splits in-sample (2023-01 … 2025-06) and OOS (2025-07 … 2025-12)
   metrics.
6. Writes the run directory and prints its path.

Inspect the report:

```bash
cat data/backtests/<run_id>/report.md
```

Re-run the same backtest. The `run_id` is identical (deterministic
re-run, exit 0 immediately).

## 5. Issue a promotion seal (if OOS clears thresholds)

Check first (no write):

```bash
uv run auto-invest promote --rule config/rules/aapl_rsi_demo.toml --backtest <run_id>
```

If the OOS metrics clear `min_oos_sharpe`, `max_oos_drawdown_pct`,
`min_oos_trade_count`, and `min_oos_window_days` (defaults from R-4),
the command prints `OK: thresholds clear`. Otherwise it prints a
per-threshold diff and exits 8.

If thresholds clear, issue the seal:

```bash
uv run auto-invest promote --rule config/rules/aapl_rsi_demo.toml --backtest <run_id> --issue
```

Output: `seal_id=<id>`. The seal file is at
`data/promotions/<seal_id>.toml`.

## 6. Promote the rule's stage to canary

Edit `config/rules/aapl_rsi_demo.toml`, change `stage = "BACKTEST"`
to `stage = "CANARY"`. Recompute the snapshot hash by re-running
`promote --check`; if the hash changes, you must repeat steps 4-5
before the worker will accept the new content (constitution VI:
material change resets to step 1).

Start the live worker against the rule:

```bash
uv run auto-invest run --capital 10000 --config config/rules/aapl_rsi_demo.toml
```

The worker:

1. Loads the rule, computes its `snapshot_hash`.
2. Finds the latest non-revoked seal for that hash.
3. Verifies all 7 seal-verification rules pass.
4. Begins evaluating the rule against live KIS quotes during US
   regular hours, capped by spec 001's canary-stage capital share.

If any verification step fails, the worker exits non-zero with a
human-readable reason. If no seal exists, the worker exits with
"missing or stale promotion seal" — by design.

## 7. Daily live-vs-backtest divergence

After each US session closes, the daily reporter computes the
realised P&L distribution for the rule and compares to the backtest
distribution. A divergence row appears in `divergence_events` if
the gap exceeds the threshold; sustained divergence over
`divergence_alert_window_days` halts the rule (per-rule halt,
documented on the daily report).

## 8. Walk-forward variant

For strategies whose parameters are recalibrated periodically:

```bash
uv run auto-invest backtest \
    --rule config/rules/<name>.toml \
    --from 2021-01-01 \
    --to 2025-12-31 \
    --mode walkforward
```

The engine reads `mode.walkforward` from the generated run.toml
(defaults: 365-day train, 90-day test, 90-day step, ≥4 folds). The
report shows per-fold metrics plus an aggregate row; promotion
thresholds apply to the aggregated OOS metrics across folds.
