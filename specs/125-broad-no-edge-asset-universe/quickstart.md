# Quickstart: Broad NO_EDGE Asset Universe Rotation

## Focused Tests

```bash
uv run pytest tests/unit/test_broad_no_edge_asset_universe_rotation.py tests/integration/test_broad_no_edge_asset_universe_rotation_probe.py -q
```

## Manifest

```bash
uv run python scripts/broad_no_edge_asset_universe_rotation_probe.py --manifest
```

## Local Sidecar Replay

Create a temporary evidence directory with the required sidecars:

```bash
tmpdir="$(mktemp -d)"
git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md > "$tmpdir/rebalance-paper-forward.md"
git show origin/automation/money-path-last-run:LAST_RUN.md > "$tmpdir/money-path.md"
git show origin/automation/edge-autoarm-last-run:LAST_RUN.md > "$tmpdir/edge-autoarm.md"
git show origin/automation/public-data:LAST_RUN.md > "$tmpdir/public-data.md"
git show origin/automation/released-work-last-run:released_work.json > "$tmpdir/released-work.md"
git show origin/automation/autonomous-evolution-last-run:learning_ledger.json > "$tmpdir/evolution-ledger.md"
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md > "$tmpdir/pipeline-liveness.md"
uv run python scripts/broad_no_edge_asset_universe_rotation_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json \
  --now 2026-08-11T12:00:00Z
```

Expected:

- `overall_status` is not `BLOCKED`.
- `completed_candidate_id` is `candidate-broad-no-edge-asset-universe-rotation-experiment`.
- `proposed_rotation_candidates` includes separated no-live defensive rotation candidates.
- `exclusion_criteria` excludes direct repetition of the already-tested wide track.
- `released_work_summary.has_completed_candidate` is true when `--repo-root .` scans this checkout.

## Autonomous-Work Closure Replay

After the completion marker is present:

```bash
tmpdir="$(mktemp -d)"
while IFS=$'\t' read -r key branch filename; do
  git show "origin/$branch:$filename" > "$tmpdir/$key.md"
done < <(uv run python scripts/autonomous_work_execution_probe.py --manifest)
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root . \
  --json \
  --now 2026-08-11T12:00:00Z
```

Expected selected candidate: `candidate-broad-no-edge-multi-horizon-signal-experiment`.
