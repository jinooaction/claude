# Operator Quickstart — Hardened Canary

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contracts**: [contracts/](./contracts/)

## What it does

The hardened canary is the **production-deploy gate** under constitution v3.0.0 IX.B-2. Code lands on `main` via the autonomous-workflow policy (CLAUDE.md). Before any new `main` SHA reaches the live KIS worker, the canary harness validates it against:

- A 30-trading-day (L2) or 45-trading-day (L3) historical replay using spec 008's backtest engine, against both the candidate and the previous-passing baseline.
- A synthetic-shock battery on canonical adverse historical days (COVID-March-12, neg-oil-2020-04-20, yen-carry-2024-08-05, most-recent-quarterly-OPEX).
- A 10,000-iteration property-based fuzz pass over `risk/gates.py` (K1).

Five acceptance metrics are all-or-nothing. Pass ⇒ `CANARY_PASSED` audit row ⇒ deploy-eligible. Fail ⇒ `CANARY_FAILED` ⇒ NOT deploy-eligible.

## Prerequisites

1. **Spec 008 backtest engine is shipped** (commit `7f8fb99` on `main`). The canary depends on it; do NOT attempt to run the canary without it.
2. **Historical OHLCV ingested**: `python -m auto_invest.backtest ingest-history --csv-dir <dir>` must have been run for the window you intend to replay (and the four synthetic-shock dates). If the dataset is missing days, the canary exits with code `2` and a clear error.
3. **`git fetch origin`** before each canary run. The harness does NOT fetch automatically; it resolves revs against your local object store.

## First-time setup (one-shot)

```bash
# 1. Install hypothesis (added to pyproject.toml by spec 007).
uv sync

# 2. Ingest at least 60 trading days of OHLCV for the symbols your live rules use.
python -m auto_invest.backtest ingest-history --csv-dir ohlcv-csv/

# 3. (Optional) Pre-ingest the four synthetic-shock dates.
python -m auto_invest.backtest ingest-history --csv-dir ohlcv-csv/2020/  # COVID + neg-oil
python -m auto_invest.backtest ingest-history --csv-dir ohlcv-csv/2024/  # yen-carry

# 4. Confirm config/canary_bands.toml ships with sensible defaults (it does).
cat config/canary_bands.toml
```

## Running a canary

```bash
# 5. Run the full canary against HEAD vs the last canary-passed baseline (or origin/main fallback).
python -m auto_invest.canary run --tier L2

# Or pin specific revs:
python -m auto_invest.canary run \
    --candidate-rev <new-sha> \
    --baseline-rev <old-sha> \
    --tier L2
```

The harness prints a one-line status per stage and writes its full artefact tree under `data/canary/<run_id>/`.

### Reading the result

```bash
# Audit-log truth source:
sqlite3 data/audit.sqlite "
  SELECT ts_utc, event_type, payload
  FROM audit_log
  WHERE correlation_id = '<canary_run_id>'
  ORDER BY ts_utc;
"

# Forensic JSON:
jq . data/canary/<canary_run_id>/canary-run.json

# Metric table:
cat data/canary/<canary_run_id>/metrics.csv

# Fuzz counterexamples (empty file on pass):
jq . data/canary/<canary_run_id>/property-fuzz/counterexamples.json
```

A passing canary emits `CANARY_PASSED`. To use it for a real deploy: once spec 006's deploy runner ships, it will consult the most recent `CANARY_PASSED` row matching the candidate SHA and proceed iff one exists. Until spec 006 runner ships, the operator may deploy manually after confirming `CANARY_PASSED` is present.

## Kernel-touching candidate

If the candidate diff intersects `kernel.toml` paths (K1..K6, K-meta), the harness emits an additional `CANARY_KERNEL_TOUCH_DETECTED` audit row BEFORE the metric battery runs. The metric battery still runs and decides pass/fail; the kernel touch is a forensic callout, not a block (constitution v3.0.0 IX.A).

```bash
# Find every kernel-touching canary run:
sqlite3 data/audit.sqlite "
  SELECT correlation_id, payload
  FROM audit_log
  WHERE event_type = 'CANARY_KERNEL_TOUCH_DETECTED'
  ORDER BY ts_utc DESC;
"
```

## Common failure modes

| Exit | Likely cause | Action |
|------|--------------|--------|
| `1`  | `CANARY_FAILED` | Open `canary-run.json.failing_metrics`; for each, read the corresponding spec-008 artefact under `replay-window/{candidate,baseline}/` to localise the regression. |
| `2`  | Historical dataset incomplete | `python -m auto_invest.backtest ingest-history ...` for the missing dates. |
| `3`  | Internal error | `data/canary/<run_id>/error.log` has the traceback. Common cause: malformed `config/canary_bands.toml`. |
| `4`  | CLI usage error | Re-read `python -m auto_invest.canary run --help`. |

## Amending acceptance bands

Edit `config/canary_bands.toml` in a PR. Defaults ship per spec FR-C01 / FR-C02. The two "must equal 0" metrics (`risk_gate_violations`, `audit_integrity_failures`) are NOT operator-amendable in v1 (loader rejects non-zero); softening either requires a spec amendment.

## Amending the synthetic-shock date set

This is a **spec 008** concern (the date set lives in `config/synthetic_shocks.toml`, owned by spec 008). The canary reuses spec 008's resolver. Editing the date set is K-meta-adjacent (the safety surface) per spec 007 promotion criteria; the operator owns those edits.

## Sub-command shortcuts

```bash
# Synthetic-shock pass only — useful when investigating one adverse day:
python -m auto_invest.canary shock --candidate-rev HEAD --baseline-rev origin/main

# Property-fuzz pass only — useful after editing risk/gates.py to verify the math holds:
python -m auto_invest.canary fuzz --iterations 100000
```

## Reproducibility

To re-run a previous canary forensically:

```bash
# Find the seed bundle:
jq '.seed_bundle' data/canary/<canary_run_id>/canary-run.json

# Re-run with identical inputs:
python -m auto_invest.canary run \
    --candidate-rev <canary-run-json's candidate_rev> \
    --baseline-rev <canary-run-json's baseline_rev> \
    --tier <canary-run-json's tier> \
    --hypothesis-seed <seed_bundle.hypothesis_database_seed>

# The new canary-run.json MUST be byte-identical MODULO started_at / finished_at / canary_run_id.
```

SC-C04 guarantees this. Any drift is a bug; please file with the new and old `canary-run.json` side-by-side.

## What this DOES NOT do

- **Does not deploy.** It only emits the `CANARY_PASSED` / `CANARY_FAILED` signal. Deploy automation is spec 006's job.
- **Does not touch live capital.** v1 is replay-only. A future v2 may add a live 5%-capital follow-on canary; that is a separate spec.
- **Does not call live LLM.** Inherited from spec 008's backtest engine via `BACKTEST_MODE=1`.
- **Does not block kernel touches at the merge boundary.** Under constitution v3.0.0 the Kernel is a forensic-attention list, not a merge or deploy barrier. Kernel touches still pass through the metric battery; the only difference is the extra `CANARY_KERNEL_TOUCH_DETECTED` audit row.
