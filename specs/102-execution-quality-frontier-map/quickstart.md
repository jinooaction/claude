# Quickstart: Execution Quality Frontier Map

## Focused unit checks

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

Expected:

- `execution_quality_frontier_map` is deterministic in JSON.
- Markdown contains `## 체결 품질 frontier 지도`.
- Before release, selected work remains `candidate-execution-quality-frontier-map`.
- After release, selected work advances to `candidate-broker-rejection-taxonomy-contract`.

## Probe manifest check

```bash
uv run python scripts/autonomous_work_execution_probe.py --manifest
```

Expected manifest includes:

```text
execution-quality	automation/execution-quality-last-run	LAST_RUN.md
kis-smoke	automation/kis-smoke-last-run	LAST_RUN.md
rebalance-micro-gtaa	automation/rebalance-micro-gtaa-last-run	LAST_RUN.md
```

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
  | jq '{selected_candidate:.selected_work.candidate_id, execution_quality_frontier_map:.execution_quality_frontier_map}'
```

Expected before this spec is released:

- `selected_candidate` is `candidate-execution-quality-frontier-map`.
- `execution_quality_frontier_map[0].recommended_candidate_id` is `candidate-broker-rejection-taxonomy-contract`.

