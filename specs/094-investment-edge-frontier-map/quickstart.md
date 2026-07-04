# Quickstart: Investment Edge Frontier Map

## Focused tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py
```

Expected:

- Existing macro/frontier tests continue to pass.
- When `candidate-investment-edge-frontier-map` is not released, it remains selected.
- When `candidate-investment-edge-frontier-map` is released, `candidate-forward-regime-edge-experiment` is selected.
- JSON output includes `investment_edge_frontier_map`.
- Markdown output includes `## 투자 엣지 frontier 지도`.

## Local sidecar replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root . \
  --json \
  --now 2026-07-04T12:00:00Z \
  | jq '{candidate_id:.selected_work.candidate_id,status:.selected_work.status,investment_edge_frontier_map:.investment_edge_frontier_map}'
```

Expected before this spec is released:

- `selected_work.candidate_id` remains `candidate-investment-edge-frontier-map`.
- `investment_edge_frontier_map[0].recommended_candidate_id` is `candidate-forward-regime-edge-experiment`.

## Full merge gate

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
