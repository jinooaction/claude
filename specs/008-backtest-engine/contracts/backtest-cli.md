# Contract — Backtest CLI

Two new subcommands added to the existing `auto-invest` Typer application:

- `auto-invest ingest-history` — one-shot OHLCV ingest from operator-provided CSVs.
- `auto-invest backtest` — run a backtest against an ingested dataset.

## `auto-invest ingest-history`

```text
Usage: auto-invest ingest-history --from-dir PATH [--out-dir PATH]

Options:
  --from-dir PATH    REQUIRED. Directory of <SYMBOL>.csv files (see ohlcv-csv.md).
  --out-dir  PATH    Default: data/history. Versioned subdirectory is created under it.
  --dry-run          Validate CSVs and print what WOULD be ingested; write nothing.
  --verbose          Print per-file progress; default is one summary line.
  --help             Show usage and exit.
```

Exit codes:

| Code | Meaning |
|------|---------|
| 0    | Success. Stdout's last line is the new `dataset_version` hex. |
| 64   | Usage error (bad flags, missing dir). |
| 65   | One or more CSV files failed validation. Stderr lists `(file, rule, line)` for each. |
| 73   | Out-dir not writable. |

Side effects:

- Creates `data/history/<dataset_version>/` (or `--out-dir/<dataset_version>/`).
- Writes one `<SYMBOL>.parquet` per input CSV, plus `manifest.json`.
- Emits NO audit-log rows. Ingest is filesystem-only; principle IV applies to runtime audit, not to data preparation.

Idempotency: re-running with byte-identical inputs is a no-op and exits 0 with the existing `dataset_version` printed.

## `auto-invest backtest`

```text
Usage: auto-invest backtest [OPTIONS]

Options:
  --rules PATH                REQUIRED. Path to rules TOML file (same format as the live worker).
  --from DATE                 Inclusive session-date start. Format: YYYY-MM-DD.
  --to   DATE                 Inclusive session-date end.   Format: YYYY-MM-DD.
  --dataset-version HEX64     Optional. Defaults to the most recent under data/history/.
  --invoker {cli,canary}      Default: cli. The hardened-canary harness (spec 007) sets this to "canary".
  --replay-seed INT           Default: 0. Reserved for future stochastic strategies.
  --synthetic-shock           If set, ignore --from/--to and replay the four canonical shock dates
                              from config/synthetic_shocks.toml (FR-B09). Aggregates per-day.
  --out-dir PATH              Default: data/backtest. Per-run subdirectory created under it.
  --allow-kernel-edits        Bypass the kernel-touched-tree check (R-B8). Logged on use.
  --help                      Show usage and exit.
```

Exit codes:

| Code | Meaning |
|------|---------|
| 0    | Backtest completed successfully. Stdout's last line is the `run_id`. |
| 64   | Usage error. |
| 65   | Rules TOML failed validation (existing live-worker validator). |
| 66   | Dataset coverage incomplete for the requested range. Stderr lists missing (symbol, date) pairs (FR-B10). |
| 77   | Wall-clock leak detected mid-run; partial artefacts under `data/backtest/<run_id>/` are kept for forensics. |
| 78   | Working tree has uncommitted Kernel modifications and `--allow-kernel-edits` was not set. |
| 79   | A real LLM call was attempted during the run (`BACKTEST_JUDGMENT_LEAK`). |
| 80   | A non-mock broker adapter reached the router (`BACKTEST_LIVE_BROKER_LEAK`). |
| 81   | `run_id` collision in the audit log (extremely unlikely; surfaced as a hard fail per User Story 1 acceptance #3). |

Stdout layout (always):

```text
backtest run_id: 0193b8c4-...                       # first line, parseable
dataset_version: 7a8d2c...
ruleset_sha256:  3f1e9b...
date range:      2024-05-13 → 2025-05-13            (or "synthetic-shock" mode)
artefacts:       data/backtest/<run_id>/

<summary block — the operator-readable per-rule headline metrics; matches summary.md>

backtest run_id: 0193b8c4-...                       # last line, parseable
```

Stderr is used only for warnings and validation errors. The run_id line is duplicated at top and bottom so both `head -1` and `tail -1` work for scripting.

## `auto-invest backtest --synthetic-shock`

- Ignores `--from`/`--to`; uses the dates in `config/synthetic_shocks.toml`.
- Produces ONE `run_id` covering all shock days; per-day per-rule artefacts go under `per-rule/<rule_id>/by-date/<date>/`.
- This is the mode spec 007's hardened canary harness calls.

## Kernel-guard pre-flight

Before doing any other work, `backtest` runs:

```text
git status --porcelain
↓ parse
auto_invest.deploy.kernel_guard.kernel_diff_check(paths)
↓
if report.touched and not --allow-kernel-edits:
    write ERROR audit row (reason="BACKTEST_BLOCKED_KERNEL_TOUCH")
    exit 78
```

The audit row carries the offending paths so a later forensic review can see exactly what was edited at run time.

## What the CLI does NOT do

- It does NOT load `.env` or any KIS / Anthropic credentials. A backtest never needs them.
- It does NOT connect to KIS or Anthropic at any point in the run.
- It does NOT modify the live worker's SQLite DB schema. New event types are added by the K4 one-line audit.py update at merge time, before the CLI is invoked.
- It does NOT update operator rules, the whitelist, or sizing caps.
