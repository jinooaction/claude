# Contract — `config/canary_bands.toml`

**Author**: spec 007 (this PR)
**Path on disk**: `config/canary_bands.toml`
**Producer**: operator (initial defaults shipped with this PR; subsequent edits via operator PRs)
**Consumer**: `auto_invest.canary.bands.load_bands`

## Schema

```toml
# Each [<tier>] table is optional but at least one MUST be present.
# Tier names are restricted to: L2, L3. L1 is rejected (no canary needed for L1).
# A future operator amendment may add L4; the loader is forward-compatible.

[L2]
trading_days = 30                       # int, MUST be >= 30 per FR-C02; <30 is rejected
pnl_drawdown_pct = 3.0                  # float >= 0; FR-C01 #1
risk_gate_violations = 0                # int MUST be 0 per FR-C01 #2; any other value is rejected
audit_integrity_failures = 0            # int MUST be 0 per FR-C01 #3; any other value is rejected
latency_p95_regression_pct = 20.0       # float >= 0; FR-C01 #4
llm_cost_regression_pct = 10.0          # float >= 0; FR-C01 #5

[L3]
trading_days = 45                       # int MUST be >= 45 per FR-C02; <45 is rejected
pnl_drawdown_pct = 2.0
risk_gate_violations = 0
audit_integrity_failures = 0
latency_p95_regression_pct = 15.0
llm_cost_regression_pct = 7.5
```

## Loader contract

`auto_invest.canary.bands.load_bands(path: Path) -> dict[str, TierBands]`:

- Parses TOML via `tomllib`.
- Validates each section against `TierBands` pydantic model.
- Rejects: missing required keys, negative numbers, `risk_gate_violations != 0`, `audit_integrity_failures != 0`, `trading_days < 30` for L2, `trading_days < 45` for L3, unknown tier names other than `L2`/`L3`/`L4`.
- Raises `CanaryBandsConfigError` (subclass of `ValueError`) on any violation.
- Returns a frozen dict of `{tier: TierBands(...)}`.

## Why `risk_gate_violations` and `audit_integrity_failures` are pinned at 0

FR-C01 explicitly says these two metrics MUST equal 0 (any non-zero value rejects the change). They are NOT operator-amendable bands — they are operator-amendable defaults that ARE 0. The loader rejects any other value to surface operator mistakes early. If a future spec wants to soften these to `<= N`, that requires a spec amendment plus a constitution-check, NOT a config edit.

## Amendment workflow

To change a band, the operator opens a PR modifying `config/canary_bands.toml`. The PR is autonomous-merge-eligible (it does not touch the Kernel) under v3.0.0 IX.D. The next `canary run` invocation picks up the new bands; previously-recorded `canary-run.json` artefacts retain the old `bands_snapshot` in their `CANARY_ENTERED` audit payload for forensic reproducibility.

The shipped defaults in this PR are derived directly from FR-C01 / FR-C02 in spec.md. They are intentionally conservative; future tightening is expected.
