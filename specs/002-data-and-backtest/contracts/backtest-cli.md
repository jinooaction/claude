# Contract: Backtest / Promote / Data CLI

This contract documents the new `auto-invest` subcommands introduced
by spec 002. CLI is implemented in `src/auto_invest/cli.py` (Typer).

All commands write to stdout in plain text by default and to stderr
on errors. A `--json` flag on every command emits machine-readable
output suitable for CI piping. Exit codes follow POSIX (0 = success,
non-zero = failure with a documented meaning per command).

---

## `auto-invest backtest`

Run a backtest of a rule (or a programmatic strategy) against
historical data.

### Synopsis

```
auto-invest backtest --rule <path> --from <date> --to <date> [options]
auto-invest backtest --config <path>
```

### Flags

| flag | type | required | description |
|---|---|---|---|
| `--rule` | path | one of `--rule` / `--config` | path to a TOML rule (spec 001 shape) or to a Python module exposing a `Strategy` symbol |
| `--config` | path | one of `--rule` / `--config` | path to a `BacktestConfig` TOML (see `backtest-config.md`) |
| `--from` | ISO date | with `--rule` | inclusive start of the window (UTC) |
| `--to` | ISO date | with `--rule` | exclusive end of the window (UTC) |
| `--vendor` | string | no | per-run vendor pin; defaults from `config/data.toml` |
| `--instrument` | repeatable string | no | `<asset_class>:<venue>:<symbol>` triples; defaults to the symbols declared in the rule |
| `--mode` | enum | no | `single` (default) / `walkforward` / `oos` |
| `--oos-from` | ISO date | when `--mode oos` | inclusive start of the OOS reservation |
| `--oos-to` | ISO date | when `--mode oos` | exclusive end |
| `--seed` | int | no | RNG seed; defaults to 0 |
| `--max-runtime-seconds` | int | no | hard runtime budget; abort with exit 5 past the budget |
| `--json` | flag | no | machine-readable result on stdout |
| `--dry-run` | flag | no | validate config + data availability, do not execute |

### Behaviour

1. Resolves config:
   - `--config` form: load and validate the TOML.
   - `--rule` form: build an in-memory `BacktestConfig` from flags
     and write it to `data/backtests/<run_id>/inputs/run.toml`
     before the run starts.
2. Computes `run_id` from `(rule_snapshot_hash, config_hash, data_pin_hash)`.
3. If `data/backtests/<run_id>/` already exists with a terminal
   `result_status`, prints the existing report path and exits 0
   (idempotent re-run).
4. Otherwise creates the run directory and starts the engine.
5. Streams progress to stderr; final report path to stdout.
6. Writes a terminal-state row to `backtest_runs`.

### Exit codes

| code | meaning |
|---|---|
| 0 | Run completed successfully (or idempotent re-run hit). |
| 1 | Config validation failed. |
| 2 | Insufficient data (gap, missing warm-up, blocked-severity DQ event). |
| 3 | LookaheadError: strategy attempted post-decision read. |
| 4 | Risk gate divergence detected (live router and backtest router disagree). |
| 5 | Aborted by `--max-runtime-seconds`. |
| 6 | I/O failure (could not write run directory, etc.). |

---

## `auto-invest promote`

Issue or revoke a promotion seal binding a rule snapshot to a
backtest run.

### Synopsis

```
auto-invest promote --rule <path> --backtest <run_id> [--issue]
auto-invest promote --revoke <seal_id> --reason <text>
auto-invest promote --check <rule>
```

### Flags

| flag | type | description |
|---|---|---|
| `--rule` | path | rule TOML to be sealed |
| `--backtest` | string | `run_id` of a successful, OOS-bearing backtest |
| `--issue` | flag | actually write the seal (default is `--check` semantics: verify thresholds, do not write) |
| `--revoke` | string | `seal_id` to revoke |
| `--reason` | text | free-text revocation reason; required with `--revoke` |
| `--check` | path | inspect existing seals for a rule and print their status |

### Behaviour (issue path)

1. Load the rule, compute `rule_snapshot_hash`, fail if it does
   not match the `rule_snapshot_hash` recorded in the backtest run.
2. Load the backtest run's OOS metrics (if `--mode` was `oos` or
   `walkforward`; otherwise fail with exit 7).
3. Compare against `PromotionThresholds`. On any miss, print a
   per-threshold diff and exit 8.
4. On all-pass, write the seal TOML and a row to `promotion_seals`,
   print the `seal_id`.

### Exit codes

| code | meaning |
|---|---|
| 0 | Success (seal issued, revoked, or check passed). |
| 1 | Config / argument error. |
| 7 | Backtest run lacks OOS metrics. |
| 8 | OOS metrics fail one or more thresholds. |
| 9 | Seal not found (revoke / check). |

---

## `auto-invest data`

Inspect the unified data store.

### Synopsis

```
auto-invest data describe [--asset-class <ac>] [--venue <v>] [--symbol <s>] [--kind <k>]
auto-invest data ingest --adapter <name> --from <date> --to <date> [--instrument <ac:venue:symbol>...]
auto-invest data revisions --instrument <ac:venue:symbol> --kind <k> --ts <iso>
```

### `data describe`

Reports per `(asset_class, venue, symbol, kind, vendor)`: earliest
record, latest record, gap count, last revision time, vendor count.
Optional filters narrow the query. Always reads the `is_adjusted=0`
unadjusted view unless `--adjusted` is set.

### `data ingest`

Drives an `IngestionAdapter` for a window. The adapter is named by
its registry key (`kis_us_equity`, `crypto_public`, etc.) and must
appear in `enabled_adapters` in `config/data.toml`. Records are
written via the standard append + revision path; adapters cannot
mutate existing rows.

Exit code 2 on rate-limit / breaker open with retry exhausted.

### `data revisions`

Lists every recorded revision for one
`(instrument, kind, content-ts)`, ordered by `as_of_ts_utc`. Useful
when chasing a discrepancy between two backtest runs that should
have produced identical output.

---

## Compatibility notes

- All existing spec 001 commands (`run`, `db migrate`, `halt`,
  `resume`, `status`, `report`, `version`) are unchanged in behaviour.
- `auto-invest run` gains one new failure mode: a rule without a
  valid promotion seal is rejected at startup with exit code 11
  ("missing or stale promotion seal"). The `--unsealed-development`
  flag bypasses this gate **only** in combination with `--dry-run`.
