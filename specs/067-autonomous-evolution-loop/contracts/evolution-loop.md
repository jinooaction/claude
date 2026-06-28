# Contract: Autonomous Evolution Loop

## Read-Only Scan Command

Planned command:

```bash
uv run auto-invest evolution-scan \
  --evidence-dir <dir> \
  --ledger-json <path> \
  --summary-out <path> \
  --json-out <path>
```

### Inputs

- `--evidence-dir`: Directory containing collected evidence files. The implementation may populate this from sidecars, specs, and local probes before calling the pure core.
- `--ledger-json`: Existing learning ledger. Missing file means an empty ledger.
- `--summary-out`: Markdown latest-run summary destination.
- `--json-out`: Machine-readable latest-run JSON destination.
- Future optional flags may include `--as-of`, `--domain`, and `--max-candidates`.

### Outputs

- Markdown summary in Korean.
- JSON summary matching `EvolutionRunSummary`.
- Updated learning ledger when candidate state changes.

### Exit Codes

- `0`: Scan completed, even if no actionable candidate exists.
- `1`: Internal scan failure or invalid input JSON.
- `2`: Contract violation such as an unmasked secret-like value in output, invalid candidate state transition, or attempted direct money-path action.

## Safety Contract

The scan command must be able to run without broker secrets and without network access after evidence collection. It must not call broker APIs, place orders, modify live strategy configuration, modify capital sentinels, change whitelists, relax caps, or alter the constitution/kernel.

Candidates that require those actions are output as `operator_review` or existing-gate inputs only.

## Sidecar Contract

Planned sidecar branch:

```text
automation/autonomous-evolution-last-run
```

Files:

```text
LAST_RUN.md
evolution_summary.json
learning_ledger.json
candidate_backlog.json
```

`LAST_RUN.md` must include:

- `timestamp_utc`
- `commit`
- top breakthrough candidates
- safe high-leverage work inside existing gates
- evidence-dependency items, including market-observation dependencies when relevant
- safety-boundary review items
- stale evidence
- explicit statement that no orders, capital, whitelist, or cap changes were made

## Probe Contract

Planned script:

```bash
uv run python scripts/evolution_loop_probe.py --manifest
uv run python scripts/evolution_loop_probe.py --evidence-dir <dir> --json
uv run python scripts/evolution_loop_probe.py --evidence-dir <dir>
```

`--manifest` prints sidecar evidence requirements as:

```text
key<TAB>branch<TAB>filename
```

This mirrors existing money-path and pipeline-liveness probe patterns.
