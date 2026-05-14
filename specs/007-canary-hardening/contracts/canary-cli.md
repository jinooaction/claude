# Contract — Canary CLI

**Module**: `python -m auto_invest.canary` (entrypoint `src/auto_invest/canary/__main__.py`)
**Author**: spec 007 (this PR)
**Consumers**: operator-instructed sessions; future spec 005 autonomous tuner; future spec 006 deploy runner (read-only consumer of `CANARY_PASSED` audit rows).

## Subcommands

### `canary run`

Full battery: replay-window + synthetic-shock + property-fuzz + 5-metric evaluation.

```
python -m auto_invest.canary run \
    [--candidate-rev <ref-or-sha>]      # default: HEAD
    [--baseline-rev <ref-or-sha>]       # default: most recent CANARY_PASSED.candidate_rev, fallback origin/main (per R-C1)
    --tier {L2,L3}                       # REQUIRED; L1 rejected (no canary needed for L1 per spec 005)
    [--window-trading-days <int>]       # default: from config/canary_bands.toml [<tier>].trading_days
    [--bands-toml <path>]               # default: config/canary_bands.toml
    [--data-source <name>]              # default: csv (passes through to spec 008's CSVDataSource)
    [--history-dir <path>]              # default: data/history/
    [--hypothesis-seed <int>]           # default: derived from canary_run_id
    [--hypothesis-iterations <int>]     # default: 10000 (FR-C04 minimum)
    [--run-id <uuid>]                   # default: generated UUID4
    [--shocks-toml <path>]              # default: config/synthetic_shocks.toml (spec 008's)
    [--audit-db <path>]                 # default: data/audit.sqlite (shared with worker + backtest)
    [--out-dir <path>]                  # default: data/canary/<run_id>/
    [--dry-run]                         # parse args + resolve revs; do NOT emit CANARY_ENTERED
```

### `canary shock`

Synthetic-shock pass ONLY (operator forensic / debug use).

```
python -m auto_invest.canary shock \
    --candidate-rev <ref-or-sha>
    --baseline-rev <ref-or-sha>
    [--shocks-toml <path>]              # default: config/synthetic_shocks.toml
    [--out-dir <path>]                  # default: data/canary/<run_id>/shock-replay/
```

Emits `CANARY_ENTERED` + per-shock `BACKTEST_*` rows + a `CANARY_FAILED` if any shock surfaces a risk-gate violation or audit-integrity issue; emits `CANARY_PASSED` otherwise. Skips replay-window and property-fuzz.

### `canary fuzz`

Property-fuzz pass ONLY (operator forensic / debug use).

```
python -m auto_invest.canary fuzz \
    [--iterations <int>]                # default: 10000
    [--seed <int>]                      # default: random; recorded in seeds.txt
    [--out-dir <path>]                  # default: data/canary/<run_id>/property-fuzz/
```

Does NOT emit audit events — pure forensic / iteration tool.

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | `canary run` → `CANARY_PASSED`. `canary shock` → all shocks clean. `canary fuzz` → zero counterexamples. |
| `1`  | `canary run` → `CANARY_FAILED` (any metric outside band, any gate violation in shock, any fuzz counterexample). |
| `2`  | Data-incomplete: spec 008's historical dataset is missing days inside the requested window. Operator action: `python -m auto_invest.backtest ingest-history ...`. (FR-implicit edge case from spec.) |
| `3`  | Internal error: uncaught exception, IO error on `data/canary/`, malformed `config/canary_bands.toml`, etc. Stack trace written to `data/canary/<run_id>/error.log` if `run_id` was allocated. |
| `4`  | CLI usage error (bad flags, invalid `--tier`, conflicting flags). Conventional argparse exit. |

## Constraints on rev resolution

- `--candidate-rev` MUST resolve via `git rev-parse` to a single SHA-40. Symbolic refs (`HEAD`, `origin/main`, tag names) are accepted and resolved at run start. Resolved SHA is recorded in `canary-run.json`.
- `--baseline-rev` SAME, with the auto-resolution fallback chain per R-C1.
- Both revs MUST be reachable from `origin/*` OR the local working repo. The harness does NOT fetch automatically (operator must `git fetch origin` first); if a rev cannot be resolved the harness exits with code `4`.

## Side-effect contract

A successful (exit-0) `canary run` invocation:

1. Reads from disk: `kernel.toml`, `config/canary_bands.toml`, `config/synthetic_shocks.toml`, `data/history/<dataset_version>/`, the git object store.
2. Writes to disk: `data/canary/<run_id>/**`, plus N+M+1 audit rows into `data/audit.sqlite` (where N = number of replay days × 2 revs, M = number of shock days × 2 revs, +1 for `CANARY_ENTERED`/`CANARY_PASSED`/`CANARY_FAILED`/`CANARY_KERNEL_TOUCH_DETECTED` as applicable).
3. Does NOT touch: `.env`, the KIS broker, the Anthropic API, any network destination.

Anyone observing point 3 by running `tcpdump` during the canary should see ZERO outbound network traffic. This is verified by `tests/integration/test_canary_no_network.py` using a mock socket guard.
