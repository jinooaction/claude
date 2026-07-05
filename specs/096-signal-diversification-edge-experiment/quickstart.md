# Quickstart: Signal Diversification Edge Experiment

## Focused Tests

```bash
uv run pytest tests/unit/test_signal_diversification_edge_experiment.py \
  tests/integration/test_signal_diversification_edge_experiment_probe.py
```

Expected: focused tests pass.

## Latest Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/signal_diversification_edge_experiment_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/signal_diversification_edge_experiment_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json \
  | jq '{status:.overall_status, metrics:.diversification_metrics, candidates:.proposed_signal_candidates, money:.money_state}'
```

Expected:

- `completed_candidate_id` is `candidate-signal-diversification-edge-experiment`.
- required inputs include all five sidecars.
- `signal_families` and `proposed_signal_candidates` are present.
- money state remains read-only and does not enable orders.

## Candidate Closure Replay

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '.released_work[] | select(.candidate_id=="candidate-signal-diversification-edge-experiment")'
```

Expected: released-work includes the completed candidate.

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json \
  | jq '{selected_candidate:.selected_work.candidate_id, investment_edge_frontier_map:.investment_edge_frontier_map}'
```

Expected: selected candidate advances to `candidate-cost-adjusted-edge-experiment`.

## Final Gates

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
