# Quickstart: Agent Ops Frontier Map

## Focused Unit Tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

Expected:

- Existing macro, investment, data, and execution-quality frontier tests continue to pass.
- When `candidate-agent-ops-frontier-map` is not released, it remains selected.
- When `candidate-agent-ops-frontier-map` is released, `candidate-handoff-truth-liveness-contract` is selected.
- JSON includes `agent_ops_frontier_map`.
- Markdown includes `## 운영 체계 frontier 지도`.

## Probe Integration

```bash
uv run pytest tests/integration/test_autonomous_work_execution_probe.py -q
```

Expected:

- Manifest and repo-root modes still parse required evidence.
- JSON output includes `agent_ops_frontier_map`.

## Local Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py --evidence-dir "$tmpdir" --repo-root . --json \
  | jq '{candidate_id:.selected_work.candidate_id,status:.selected_work.status,agent_ops_frontier_map:.agent_ops_frontier_map}'
rm -rf "$tmpdir"
```

Expected when replaying remote sidecars without the local repo-root override:

- `candidate_id` is `candidate-agent-ops-frontier-map`.
- `agent_ops_frontier_map[0].recommended_candidate_id` is `candidate-handoff-truth-liveness-contract`.

With `--repo-root .`, released-work scans the current checkout and sees the spec 106 marker; the next selected work becomes `candidate-handoff-truth-liveness-contract`.

## Full Gate

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
