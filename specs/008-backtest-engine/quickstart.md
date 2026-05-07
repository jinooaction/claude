# Quickstart: Backtest Engine

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Date**: 2026-05-07

This is the operator-facing onboarding path. It gets you from "I have a candidate rule" to "I have a deterministic returns/drawdown/Sharpe report" in five steps.

## Prerequisites

- The auto-invest project's existing `uv` venv is active (spec 001).
- `data/auto_invest.db` exists and has migrations `0001_initial.sql`, `0002_token_usage.sql`, **and `0003_backtest_events.sql`** applied. (After spec 008 lands, the migration runner applies 0003 automatically on startup.)
- Outbound HTTPS works for whichever vendor you select (`yfinance` ↔ Yahoo; `kis_historical` ↔ KIS REST).
- For `kis_historical`: KIS app key/secret are in `.env`, identical to live trading.
- Working tree is clean: `git status` shows nothing pending. (Dirty trees produce `<sha>+dirty` and are rejected by spec 007's canary harness; v1 ad-hoc exploration with `--allow-dirty` is fine but those runs cannot promote.)

## Step 1 — Pick or write a rule TOML

Use the existing rule TOML schema (spec 001 contract `rules-config.md`). Example minimal SMA-cross rule:

```toml
# rules/sma_cross.toml
[[rules]]
id = "sma_cross_aapl"
symbol = "AAPL"
order_type = "LIMIT"          # constitution domain default
side = "BUY"
qty = 10
limit_price_offset_pct = 0.5  # buy 0.5% below the cross signal
enabled = true

[rules.trigger]
kind = "indicator"
indicator = "sma_cross"
fast_window = 20
slow_window = 50
timeframe = "1d"
```

The rule schema is owned by spec 001; spec 008 consumes it without modification. Anything that runs in live runs in backtest.

## Step 2 — Run an exploratory backtest

```bash
auto-invest backtest \
    --rules rules/sma_cross.toml \
    --window 2024-01-02:2024-12-31 \
    --symbols AAPL
```

Expected stderr (≈ 30 s for 1 symbol × 252 daily bars):

```
[008] code_sha = abc1234
[008] dataset_hash = 7f9a... (consumed 252 bars)
[008] window = 2024-01-02..2024-12-31, 252 trading days
[008] BACKTEST_STARTED audit row appended (run_id=8e1f...c2)
[008] replay 252/252 ▮▮▮▮▮▮▮▮▮▮ (28.4 s)
[008] BACKTEST_COMPLETED — total_return=12.34% drawdown=4.21% sharpe=0.83
[008] verdict: promote_eligible=true
```

Stdout is one line:

```
data/backtests/8e1f...c2/
```

## Step 3 — Read the headline report

```bash
cat data/backtests/8e1f...c2/report.json | python -m json.tool
```

You'll see `total_return_pct`, `max_drawdown_pct`, `sharpe_annualised`, the per-rule P&L breakdown, and the `verdict.reasons` array — three lines, one per acceptance threshold.

If `promote_eligible: true` and the rule is sane (you understand why each fill happened), step 4. If `false`, return to step 1 — the rule is wrong, the window is wrong, or your expectations were wrong.

## Step 4 — Verify reproducibility

Reproducibility is the contract spec 007's canary harness rests on. Quick sanity check:

```bash
# Re-run with the same seed; verify byte-identical output.
RUN1=$(auto-invest backtest --rules rules/sma_cross.toml --window 2024-01-02:2024-12-31 --symbols AAPL --seed 0)
RUN2=$(auto-invest backtest --rules rules/sma_cross.toml --window 2024-01-02:2024-12-31 --symbols AAPL --seed 0)

diff <(jq 'del(.start_ts_utc,.end_ts_utc,.dirty)' "$RUN1/manifest.json") \
     <(jq 'del(.start_ts_utc,.end_ts_utc,.dirty)' "$RUN2/manifest.json")
diff "$RUN1/report.json" "$RUN2/report.json"
diff "$RUN1/daily.csv"   "$RUN2/daily.csv"
diff "$RUN1/fills.csv"   "$RUN2/fills.csv"
```

All four `diff`s must be empty. If any aren't, the engine has a determinism regression — file a bug, do not promote anything.

## Step 5 — Run synthetic-shock replay

```bash
auto-invest backtest \
    --rules rules/sma_cross.toml \
    --vendor yfinance \
    --named synthetic_shock_v1
```

This is the same battery the spec 007 canary harness will run as one of its FR-C03 gates. v1 has four dates (2020-03-12, 2020-04-20, 2024-08-05, 2026-03-20). For each date, the engine primes `warmup_bars` (default 50) of prior bars silently, then ticks once on the shock day. The per-day section of `daily.csv` shows what your rule would have done on each of those days; `fills.csv` shows whether any orders survived the gates.

If your rule produces an unexpected fill on 2020-04-20 (negative oil futures), that's a sign the rule's price-source assumptions don't survive the limit-order-only invariant. Fix the rule before promoting.

## Querying past runs from SQLite

The audit_log is the canonical record. SC-B06 says "answer 'show me every backtest run in the last 30 days, its verdict, and its dataset hash' using a single SQL query":

```sql
SELECT
    json_extract(payload, '$.run_id')               AS run_id,
    ts_utc,
    json_extract(payload, '$.total_return_pct')     AS total_return_pct,
    json_extract(payload, '$.max_drawdown_pct')     AS max_drawdown_pct,
    json_extract(payload, '$.sharpe')               AS sharpe,
    json_extract(payload, '$.promote_eligible')     AS promote_eligible
FROM audit_log
WHERE event_type = 'BACKTEST_COMPLETED'
  AND ts_utc >= datetime('now', '-30 days')
ORDER BY ts_utc DESC;
```

The migration `0003_backtest_events.sql` adds a partial index that makes this a seek not a scan.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Exit `2` "rule TOML referenced undeclared symbol" | Rule TOML symbol off the live whitelist (`config/whitelist.py`). | Add to whitelist or fix rule. |
| Exit `3` "dataset missing date YYYY-MM-DD" | Vendor returned no bar for a required date in your window. | Try a different vendor; check that the date is a US trading day; expand cache. |
| Exit `6` "dirty git tree" | You have uncommitted changes. | `git status`; commit or stash. Use `--allow-dirty` only for ad-hoc exploration that won't be promoted. |
| Exit `7` "kernel-touch refusal" | Your change set's diff intersects `kernel.toml`. | Defense in depth — it means a hand-edit accidentally touched a Kernel file. Investigate before continuing. |
| `sharpe_annualised: null` in report | The strategy went bankrupt during the window. | The rule's risk-gate config is too aggressive, or the rule logic mass-bought into a drawdown. Review `daily.csv`. |
| Reproducibility check fails | Engine determinism regression OR you (or someone) modified `config/caps.py` / `config/whitelist.py` between runs. | First check `caps_hash` / `whitelist_hash` in the two manifests. If they differ, that's the culprit. If they match, file an engine bug. |
| Run takes > 5 min for 1 year of daily data | Cache miss → vendor rate limiting. | Pre-warm the cache with a smaller window first; the second run uses cached bars. |

## Operator workflow at a glance

```text
   write rule.toml
        |
        v
   exploratory backtest    --->  read report.json    --->  iterate
   (--window 1 year)
        |
        v
   reproducibility check
   (run twice, diff all 4 files)
        |
        v
   synthetic-shock backtest
   (--named synthetic_shock_v1)
        |
        v
   feed result into existing canary stage     (post-007: spec 007's harness
   (spec 001 strategy/canary.py for now)        becomes the binding gate)
```

This is the "Backtest" arrow constitution VI requires. Until spec 007 ships, the operator (you) is the human reviewer who decides whether to promote. Post-007, the canary harness reads `data/backtests/<run_id>/report.json` directly.

## What this engine deliberately does NOT do

- It does not place orders. Ever. (FR-B09)
- It does not modify any Kernel file (FR-B02). The one-time `kernel.toml` K4 update for migration `0003_backtest_events.sql` is part of spec 008's first landing — after that, all engine work is non-Kernel.
- It does not invoke the LLM (constitution III).
- It does not model fees, taxes, or partial fills (v1 — see spec 008's "Out of scope" section).
- It does not auto-extend `synthetic_shock_v1` with new OPEX days (FR-B20). Adding a date is L4 per spec 005 and requires operator action.
