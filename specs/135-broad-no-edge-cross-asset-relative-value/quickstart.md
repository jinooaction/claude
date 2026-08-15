# Quickstart: Broad No-Edge Cross-Asset Relative Value

## Manifest

```bash
uv run python scripts/broad_no_edge_cross_asset_relative_value_probe.py --manifest
```

Expected keys:

- `rebalance-paper-forward`
- `public-data-summary`
- `regime-stratify`
- `money-path`
- `edge-autoarm`
- `released-work`
- `pipeline-liveness`

## Current Sidecar Replay

```bash
tmpdir=$(mktemp -d)
git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md > "$tmpdir/rebalance-paper-forward.md"
git show origin/automation/public-data:summary.json > "$tmpdir/public-data-summary.md"
git show origin/automation/regime-stratify-last-run:LAST_RUN.md > "$tmpdir/regime-stratify.md"
git show origin/automation/money-path-last-run:LAST_RUN.md > "$tmpdir/money-path.md"
git show origin/automation/edge-autoarm-last-run:LAST_RUN.md > "$tmpdir/edge-autoarm.md"
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md > "$tmpdir/pipeline-liveness.md"
uv run python scripts/broad_no_edge_cross_asset_relative_value_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json
```

Expected:

- `overall_status == "CONTRACT_READY"`
- `completed_candidate_id == "candidate-broad-no-edge-cross-asset-relative-value-experiment"`
- `next_candidate_id == "candidate-broad-no-edge-tail-risk-convexity-experiment"`

## Focused Tests

```bash
uv run pytest \
  tests/unit/test_broad_no_edge_cross_asset_relative_value.py \
  tests/integration/test_broad_no_edge_cross_asset_relative_value_probe.py \
  tests/unit/test_autonomous_work_execution.py \
  -k 'cross_asset_relative_value or second_wave_broad_no_edge'
```
