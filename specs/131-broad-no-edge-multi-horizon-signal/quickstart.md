# Quickstart: Broad NO_EDGE Multi-Horizon Signal

## Focused Tests

```bash
uv run pytest tests/unit/test_broad_no_edge_multi_horizon_signal.py tests/integration/test_broad_no_edge_multi_horizon_signal_probe.py -q
```

## Manifest

```bash
uv run python scripts/broad_no_edge_multi_horizon_signal_probe.py --manifest
```

## Local Sidecar Replay

Create a temporary evidence directory with the required sidecars:

```bash
tmpdir="$(mktemp -d)"
git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md > "$tmpdir/rebalance-paper-forward.md"
git show origin/automation/money-path-last-run:LAST_RUN.md > "$tmpdir/money-path.md"
git show origin/automation/edge-autoarm-last-run:LAST_RUN.md > "$tmpdir/edge-autoarm.md"
git show origin/automation/public-data:LAST_RUN.md > "$tmpdir/public-data.md"
git show origin/automation/regime-stratify-last-run:LAST_RUN.md > "$tmpdir/regime-stratify.md"
git show origin/automation/released-work-last-run:released_work.json > "$tmpdir/released-work.md"
git show origin/automation/autonomous-evolution-last-run:learning_ledger.json > "$tmpdir/evolution-ledger.md"
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md > "$tmpdir/pipeline-liveness.md"
uv run python scripts/broad_no_edge_multi_horizon_signal_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json \
  --now 2026-08-12T12:00:00Z
```

Expected:

- `overall_status` is not `BLOCKED`.
- `completed_candidate_id` is `candidate-broad-no-edge-multi-horizon-signal-experiment`.
- `proposed_signal_candidates` includes separated no-live signal/horizon candidates.
- `exclusion_criteria` excludes direct repetition of a single-horizon momentum retry.
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
  --now 2026-08-12T12:00:00Z
```

Expected broad frontier state:

- `candidate-broad-no-edge-multi-horizon-signal-experiment` has `coverage_status=released`.
- `candidate-broad-no-edge-regime-cost-robustness-experiment` has `coverage_status=open`.

The top-level `selected_work` can be a different higher-priority recovery or validation candidate if other current sidecars expose one.
