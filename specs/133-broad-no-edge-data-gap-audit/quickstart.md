# Quickstart: Broad NO_EDGE Data Gap Audit

## Build a local evidence directory from current sidecar refs

```bash
tmpdir="$(mktemp -d)"
git show origin/automation/public-data:LAST_RUN.md > "$tmpdir/public-data-last-run.md"
git show origin/automation/public-data:summary.json > "$tmpdir/public-data-summary.md"
git show origin/automation/public-data:regime.json > "$tmpdir/public-data-regime.md"
git show origin/automation/public-data:regime_timeline.csv > "$tmpdir/public-data-regime-timeline.md"
git show origin/automation/regime-stratify-last-run:LAST_RUN.md > "$tmpdir/regime-stratify.md"
git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md > "$tmpdir/rebalance-paper-forward.md"
git show origin/automation/money-path-last-run:LAST_RUN.md > "$tmpdir/money-path.md"
git show origin/automation/edge-autoarm-last-run:LAST_RUN.md > "$tmpdir/edge-autoarm.md"
git show origin/automation/released-work-last-run:released_work.json > "$tmpdir/released-work.md"
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md > "$tmpdir/pipeline-liveness.md"
```

## Run the probe

```bash
uv run python scripts/broad_no_edge_data_gap_audit_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json-out "$tmpdir/data-gap-audit.json" \
  --summary-out "$tmpdir/data-gap-audit.md" \
  --run-id local \
  --commit "$(git rev-parse HEAD)"
```

Expected current-style result:

- `completed_candidate_id` is `candidate-broad-no-edge-data-gap-audit`.
- `next_candidate_id` is `wait-for-fresh-evidence`.
- CPI publication/inflation regime gaps are visible.
- `regime_timeline.csv` has all canonical labels, but `inflation_yoy` is missing.
- The report remains read-only: no broker API, no orders, no capital allocation, no live strategy change.

## Validation

```bash
uv run pytest tests/unit/test_broad_no_edge_data_gap_audit.py tests/integration/test_broad_no_edge_data_gap_audit_probe.py tests/unit/test_autonomous_work_execution.py -k "data_gap_audit or broad_no_edge"
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
