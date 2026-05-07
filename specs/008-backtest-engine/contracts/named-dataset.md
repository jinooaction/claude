# Contract: named-dataset manifest

**Spec**: [../spec.md](../spec.md) (FR-B18, FR-B19, FR-B20) · **Plan**: [../plan.md](../plan.md) · **Date**: 2026-05-07

A named dataset is a curated, frozen set of historical days that the spec 007 hardened-canary harness uses for synthetic-shock replay. v1 ships exactly one named dataset: `synthetic_shock_v1`.

## File location

`data/ohlcv/datasets/<name>.json`

Each name maps to exactly one JSON file. The engine refuses to start a `--named <name>` run if the file is missing.

## Schema (v1)

```json
{
  "schema_version": 1,
  "name": "<dataset-name>",
  "frozen_at_utc": "<ISO 8601>",
  "dates": ["<YYYY-MM-DD>", ...],
  "rationale": {
    "<YYYY-MM-DD>": "<one-line operator-readable reason>",
    ...
  },
  "constitutional_tier": "L4",
  "mutation_policy": "<one-paragraph operator-readable rule>"
}
```

### Field constraints

| Field | Constraint |
|-------|-----------|
| `schema_version` | Integer, currently `1`. Bumping is a backward-incompatible change for the canary harness. |
| `name` | Lowercase, snake_case. Matches the file's basename (without `.json`). |
| `frozen_at_utc` | ISO 8601 UTC, recorded once at freeze time. Never re-stamped. |
| `dates` | List of ISO 8601 dates, sorted ascending. Each date MUST be a US-equity trading day per `exchange_calendars`. |
| `rationale` | Object whose keys are exactly the entries in `dates` (no extras, no missing). |
| `constitutional_tier` | Always `"L4"` for synthetic-shock datasets — modifications are operator-only per spec 005. |
| `mutation_policy` | Free-form prose; the engine does not parse it. |

## v1 frozen content: `synthetic_shock_v1`

```json
{
  "schema_version": 1,
  "name": "synthetic_shock_v1",
  "frozen_at_utc": "2026-05-07T00:00:00Z",
  "dates": ["2020-03-12", "2020-04-20", "2024-08-05", "2026-03-20"],
  "rationale": {
    "2020-03-12": "COVID circuit breakers (limit-down halts).",
    "2020-04-20": "Negative oil futures — sanity check that limit-order-only enforcement holds when prices go through zero.",
    "2024-08-05": "Yen-carry unwind — global equity drawdown with cross-asset spillover.",
    "2026-03-20": "Most recent quarterly OPEX at freeze time (third Friday of March 2026)."
  },
  "constitutional_tier": "L4",
  "mutation_policy": "Operator-only. Subsequent quarterly OPEX days do NOT auto-roll into this dataset. Adding or removing a date is L4 per spec 005 (affects the safety surface). The engine refuses to silently mutate this file."
}
```

## Mutation discipline

1. **Adding a date** is a forward-compatible safety improvement (more shock surface = more backstop). It MUST be a deliberate operator action with an audit-log `OPERATOR_ACTION` row recording rationale. The engine does NOT accept a mutation through any non-CLI path; the file is edited by hand and the change set goes through review.
2. **Removing a date** is a safety regression and MUST be paired with operator justification. It is L4 per spec 005 and goes through human review.
3. **Renaming** is forbidden. A new dataset gets a new name (`synthetic_shock_v2`); old datasets stay untouched so old artifacts remain reproducible.
4. **`schema_version` bump** is a separate review event — it implies the canary harness's reading code (spec 007) needs an update to honour the new shape.

## How the engine uses the manifest

Given `--named <name>`:

1. Load `data/ohlcv/datasets/<name>.json`.
2. Validate against the schema above; reject with exit code `2` on any deviation.
3. For each `(date, symbol)` derived from `dates × symbols`, call the chosen vendor adapter's `fetch_bars(symbol, date - warmup_bars × 1.5, date)` so the indicator state is primed (R-8). Cache hits satisfy without a network call.
4. Emit `BACKTEST_STARTED` with `named_dataset = <name>` and a hash over the canonicalised manifest in `dataset_hash`. The dataset's content hash is part of FR-B12's reproducibility floor.

## Drift detection

The run's `manifest.json` records `dataset_hash` over the loaded named-dataset JSON. Two runs against the same `synthetic_shock_v1` manifest produce the same `dataset_hash`. Any subsequent edit (adding a date, renaming the rationale) is detected as a hash difference by the canary harness, which is the explicit FR-B19 mechanism for "spec 007's harness can detect drift".
