# Contract: `auto-invest backtest` CLI subcommand

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Date**: 2026-05-07

The CLI is a thin click wrapper over `auto_invest.backtest.run_backtest`. Operators interact with this; the spec 007 hardened-canary harness imports the library function directly (R-9). Both share one `BacktestConfig` validator.

## Synopsis

```text
auto-invest backtest \
    --rules <PATH-TO-TOML> \
    [--vendor yfinance|kis_historical] \
    [--window <YYYY-MM-DD>:<YYYY-MM-DD> | --named <DATASET-NAME>] \
    [--symbols <CSV>] \
    [--seed <INT>] \
    [--opening-cash-usd <DECIMAL>] \
    [--slippage-bps-market <INT>] \
    [--risk-free-rate-annual <DECIMAL>] \
    [--warmup-bars <INT>] \
    [--output-root <PATH>] \
    [--allow-dirty] \
    [--quiet | --verbose]
```

## Required flags

| Flag | Type | Notes |
|------|------|-------|
| `--rules` | path | Absolute or repo-relative path to a rules TOML conforming to the live rule schema (spec 001 contract). |

Either `--window` or `--named` is required (mutually exclusive).

## Optional flags (with defaults)

| Flag | Default | Notes |
|------|---------|-------|
| `--vendor` | `yfinance` | One of `yfinance`, `kis_historical`. FR-B06. |
| `--window <START>:<END>` | — | Inclusive contiguous date range. ISO 8601 (`YYYY-MM-DD`). |
| `--named <NAME>` | — | One of the curated named datasets. v1 ships `synthetic_shock_v1`. |
| `--symbols` | (rules' symbol set) | Optional intersect filter. |
| `--seed` | `0` | Recorded in manifest. |
| `--opening-cash-usd` | `100000.00` | FR-B10. |
| `--slippage-bps-market` | `5` | FR-B07 market-fill slippage. Limit fills always 0 bps. |
| `--risk-free-rate-annual` | `0` | R-7. Decimal, e.g. `0.05` = 5%. |
| `--warmup-bars` | `50` | R-8. |
| `--output-root` | `data/backtests/` | Run artifact root. The run dir `<output_root>/<run_id>/` is created on success. |
| `--allow-dirty` | `false` | Allow dirty git tree. `code_sha` becomes `<sha>+dirty`; canary harness will reject. |
| `--quiet` | — | Suppress progress lines on stderr. |
| `--verbose` | — | Per-bar trace on stderr. |

## Exit codes

| Code | Meaning | Audit row emitted |
|------|---------|-------------------|
| `0` | Backtest completed; verdict may be promote_eligible or not. | `BACKTEST_COMPLETED` |
| `2` | Input validation failure (CLI parse, missing file, bad TOML, bad date). | none (fails before `BACKTEST_STARTED`) |
| `3` | OHLCV ingest failure (vendor unreachable, missing date in dataset, NaN bar). | `BACKTEST_FAILED phase=ingest_ohlcv` |
| `4` | Replay aborted (gate config invalid, runtime exception). | `BACKTEST_FAILED phase=replay` |
| `5` | Reporting/output failure (disk full, permission denied). | `BACKTEST_FAILED phase=report` |
| `6` | Dirty-tree refusal (no `--allow-dirty`). | none |
| `7` | Kernel-touch refusal — engine refuses to start if its own diff intersects `kernel.toml` (defense-in-depth, mirrors spec 007 FR-C08). | none |

## Stdout / stderr contract

- **stdout**: a single line on success — the run's artifact directory path, e.g. `data/backtests/8e1f...c2/`. Nothing else. This makes the CLI pipe-friendly.
- **stderr**: progress lines (suppressible by `--quiet`):
  ```
  [008] code_sha = abc1234
  [008] dataset_hash = 7f9a... (consumed 12,580 bars)
  [008] window = 2024-01-02..2024-12-31, 252 trading days
  [008] BACKTEST_STARTED audit row appended (run_id=...)
  [008] replay 252/252 ▮▮▮▮▮▮▮▮▮▮ (28.4 s)
  [008] BACKTEST_COMPLETED — total_return=12.34% drawdown=4.21% sharpe=0.83
  [008] verdict: promote_eligible=true
  ```
- **stderr (--verbose)**: one line per bar with `(date, fills_this_bar, gate_rejections_this_bar, equity_eod)`.

## Invariants the CLI enforces

1. The CLI validates **all** inputs *before* emitting `BACKTEST_STARTED` (FR-B16: every started run is matched by a completed-or-failed row).
2. The CLI refuses to run if its own change set's diff intersects any path under `.specify/memory/kernel.toml` — defense in depth even though the deploy guard (spec 006) already blocks deploys (exit code `7`). This mirrors spec 007 FR-C08.
3. The CLI **never** logs secrets. The KIS adapter handles its own auth via the existing `broker/auth.py` path; the CLI never sees access tokens.
4. The CLI prints the artifact directory on stdout *only after* the artifact directory has been successfully renamed into place (atomic write).

## Examples

```bash
# Operator backtests a 1-year SMA-cross rule against AAPL daily yfinance bars.
auto-invest backtest \
    --rules rules/sma_cross.toml \
    --window 2024-01-02:2024-12-31 \
    --symbols AAPL

# Spec 007 canary harness invokes synthetic-shock replay (Python entry; CLI shown for parity).
auto-invest backtest \
    --rules rules/candidate.toml \
    --vendor kis_historical \
    --named synthetic_shock_v1
```
