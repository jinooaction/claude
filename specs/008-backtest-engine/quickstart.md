# Quickstart — First Backtest in 10 Minutes

For the non-developer operator running their first backtest. Assumes the live worker (spec 001) is already running on this machine and that the operator already has a working `uv` venv.

## What this gives you

A per-rule report (return %, max drawdown %, Sharpe, fill counts) for any ruleset, over any historical window for which you have CSV data on disk. No real broker, no real LLM, no risk to capital — completely offline.

## Step 1 — Get OHLCV data into a local directory

Use whatever vendor you trust (your KIS-affiliated broker dashboard, a free CSV export from Yahoo, a paid feed, etc.). Put one CSV per symbol into a directory of your choice. Each CSV MUST match the format documented in `contracts/ohlcv-csv.md`:

```text
~/auto-invest/history-csv/
├── AAPL.csv
├── SPY.csv
└── ...
```

Each CSV must have this header row:

```text
session_date,open,high,low,close,volume,session_schedule_tag
```

…and one row per US trading day, sorted ascending. If a row fails validation (negative price, duplicate date, missing column), `ingest-history` will tell you exactly which file and which line.

> If you're not sure how to produce these CSVs from your data source, ask in the next session before running `ingest-history`. The engine will refuse to start a backtest on bad data — that's better than silently giving you a misleading report.

## Step 2 — Ingest the CSVs

```bash
cd ~/auto-invest
uv run auto-invest ingest-history --from-dir ./history-csv
```

This converts the CSVs to a versioned parquet snapshot under `data/history/<dataset_version>/` and writes a manifest. The last line of stdout is the `dataset_version` hex — write it down (or just ignore it; the next step picks the latest by default).

Validation errors print to stderr with the format `<file>:<line>: <rule>: <details>`. Fix the offending CSV and re-run.

## Step 3 — Run your first backtest

Use the same `rules.toml` you use for the live worker:

```bash
uv run auto-invest backtest \
  --rules config/rules.toml \
  --from 2024-05-13 \
  --to   2025-05-13
```

The CLI:

1. Checks `git status --porcelain` and refuses to run if any Kernel file (per `.specify/memory/kernel.toml`) has uncommitted changes. If that blocks you, commit those changes or use `--allow-kernel-edits` (which logs the bypass).
2. Loads your ruleset and validates it — same validator as the live worker.
3. Snapshots the latest `dataset_version`.
4. Replays the date range, one (symbol, session_date) at a time, against `Worker.tick` + the existing risk gates + an in-memory broker mock.
5. Writes artefacts under `data/backtest/<run_id>/` and a summary block to stdout.

What you should see at the bottom of stdout (the human-readable summary):

```text
=== Backtest summary ===
Range: 2024-05-13 → 2025-05-13   Ruleset hash: 3f1e9b…
Dataset: 7a8d2c…   Fill model: pessimistic (zero slippage)

Aggregate
  return:   3.14% gross
  drawdown: 1.87% max
  sharpe:   0.81 (annualised, RFR 0%)

Per rule
  buy_spy_open_below_50d (SPY)    ret 2.14%   dd 1.11%   sharpe 0.64   12/11/1 ord/fill/rej
  sell_aapl_close_above_band (AAPL) …
  …

Artefacts: data/backtest/<run_id>/
```

## Step 4 — Decide

Read `summary.md` under `data/backtest/<run_id>/` (or just read the stdout block above). For each rule, ask:

1. Did it fire enough to matter? (If `order_count == 0`, the rule is dormant on this data.)
2. Is the gate-rejection count what I expected? (High rejections mean the rule's qty/limits are misaligned with the caps.)
3. Is the drawdown tolerable?
4. Is the Sharpe better than the alternative I'd run instead?

If the rule passes your judgment, the next step is **canary** (spec 001's existing canary loop, 10 days at 5% capital). Spec 007 will eventually replace that with a hardened canary that uses this same backtest engine for synthetic-shock replay and property fuzz — that's the path to autonomous merge.

If the rule doesn't pass, edit the rule and re-run. The engine is deterministic, so two runs with identical inputs produce byte-identical per-rule artefacts; you can diff your changes meaningfully.

## Things that will NOT happen during a backtest

If any of these DO happen, it's a bug — please open an issue and attach the `data/backtest/<run_id>/` directory.

- A real order is sent to KIS. (Defense-in-depth: the engine fails with exit 80 and writes a `BACKTEST_LIVE_BROKER_LEAK` audit row if a non-mock adapter reaches the order router.)
- A real Anthropic call is made. (Fails with exit 79, `BACKTEST_JUDGMENT_LEAK`.)
- The system clock is read inside the replay. (Fails with exit 77, `WALL_CLOCK_LEAK`.)
- Your live worker's positions or PnL change. (Backtest artefacts go to `data/backtest/<run_id>/`; the audit log gets `BACKTEST_*` rows that `auto-invest report` and `auto-invest status` filter out by design.)

## Synthetic-shock replay (spec 007 prerequisite)

```bash
uv run auto-invest backtest --rules config/rules.toml --synthetic-shock
```

Replays the four canonical shock days (2020-03-12, 2020-04-20, 2024-08-05, most recent quarterly OPEX) against your current ruleset. Useful sanity check that your gates DO trip when they should — under a deliberately loose ruleset, you SHOULD see at least one `ORDER_REJECTED_BY_GATE` on 2020-03-12.

## Common errors and fixes

| You see                                            | What happened                                                          | Fix                                                                |
|----------------------------------------------------|-----------------------------------------------------------------------|--------------------------------------------------------------------|
| `exit 65 — Rules TOML failed validation`           | Same validator as live worker rejected your rules.                     | Fix the rules; live worker would have failed too.                  |
| `exit 66 — Dataset coverage incomplete`            | Some (symbol, date) you needed is not in the ingested data.            | Add the missing data to your CSV directory and re-run ingest.      |
| `exit 78 — Kernel-touched working tree`            | An uncommitted file in `.specify/memory/kernel.toml`'s K-set.          | Commit or stash. Use `--allow-kernel-edits` only if intentional.   |
| `exit 77 — Wall-clock leak`                        | Some code path read `datetime.now()` during the replay.                | Report — this is a bug.                                            |
| `exit 79 — Judgment leak`                          | A judgment-point module tried a real Anthropic call during the run.    | Report — `BACKTEST_MODE=1` should have switched it to stub.        |
| `exit 80 — Live broker leak`                       | A non-mock broker adapter reached the order router during the run.    | Report — high-severity safety bug.                                 |

## Files you produce, files you don't

You produce:

- One directory of CSVs (Step 1).

The engine produces:

- `data/history/<dataset_version>/...` — parquet snapshot of your CSVs.
- `data/backtest/<run_id>/...` — per-run report artefacts.
- New rows in `audit_log` with event types `BACKTEST_STARTED`, `BACKTEST_COMPLETED`, and (if spec 004 ships before this is your first backtest) `LLM_CALL_STUBBED`. These rows are filtered out of `auto-invest report` and `auto-invest status`.

The engine does NOT modify:

- Your `.env`, your rules, your whitelist, your sizing caps.
- The live worker's PnL or position cache.
- Any existing audit row.
