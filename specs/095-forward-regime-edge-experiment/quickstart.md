# Quickstart: Forward Regime Edge Experiment

## Focused Tests

```bash
uv run pytest tests/unit/test_forward_regime_edge_experiment.py tests/integration/test_forward_regime_edge_experiment_probe.py
```

## Probe Manifest

```bash
uv run python scripts/forward_regime_edge_experiment_probe.py --manifest
```

Expected keys:

- `rebalance-paper-forward`
- `money-path`
- `released-work`
- `evolution-ledger`
- `pipeline-liveness`

## Local Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/forward_regime_edge_experiment_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/forward_regime_edge_experiment_probe.py \
  --sidecar-dir "$tmpdir" \
  --json \
  --repo-root .
```

Expected current posture:

- `completed_candidate_id` is `candidate-forward-regime-edge-experiment`.
- `overall_status` is `OBSERVATION_WAIT` while forward observations remain below comparable thresholds.
- `money_state.status` is expected to be `PREVIEW_ONLY` on current sidecars.
- `safety_boundary` states no orders, no capital allocation, and no live strategy change.

## Released-Work and Next Candidate Replay

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '[.released_work[] | select(.candidate_id=="candidate-forward-regime-edge-experiment")]'

uv run python scripts/autonomous_work_execution_probe.py --sidecar-dir "$tmpdir" --repo-root . --json \
  | jq '{selected_candidate:.selected_work.candidate_id, investment_edge_frontier_map:.investment_edge_frontier_map}'
```

Expected after this spec is complete:

- released-work includes `candidate-forward-regime-edge-experiment`.
- autonomous-work advances to the next unreleased investment-edge no-live candidate.
