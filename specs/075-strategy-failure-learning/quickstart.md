# Quickstart: Strategy Failure Learning

## Local smoke with latest sidecars

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/evolution_loop_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
git show origin/automation/autonomous-evolution-last-run:learning_ledger.json \
  > "$tmpdir/learning_ledger_prior.json" 2>/dev/null || echo '{}' \
  > "$tmpdir/learning_ledger_prior.json"

uv run python scripts/evolution_loop_probe.py \
  --evidence-dir "$tmpdir" \
  --ledger-json "$tmpdir/learning_ledger_prior.json" \
  --ledger-out "$tmpdir/learning_ledger.json" \
  --json-out "$tmpdir/evolution_summary.json" \
  --summary-out "$tmpdir/LAST_RUN.md" \
  --run-id local-075

python - <<'PY' "$tmpdir/learning_ledger.json"
import json, sys
ledger = json.load(open(sys.argv[1]))
print([
    (row["candidate_id"], row["decision"], row.get("evidence_package_id"))
    for row in ledger["entries"]
    if row["candidate_id"] in {"candidate-1ed634d8bf6d", "candidate-cc96b35062da"}
])
PY
```

Expected: both candidates have `rejected` entries sourced from `autonomous-promotion:<run_id>`.

## Focused checks

```bash
uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py -q
uv run ruff check src/auto_invest/analytics/evolution_loop.py scripts/evolution_loop_probe.py tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py
```
