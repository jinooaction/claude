# Quickstart: Execution Cost Basis Contract

## Local Fixture Run

```bash
uv run python scripts/execution_cost_basis_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/execution_cost_basis.json \
  --summary-out /tmp/execution_cost_basis.md
```

Expected for current sidecar evidence:

- `overall_status` is `OBSERVATION_WAIT` when `execution-quality` lacks accepted/fill cost-basis evidence.
- `cost_basis_summary.cost_basis_state` is `COST_BASIS_OBSERVATION_WAIT`.
- `completed_candidate_id` is `candidate-execution-cost-basis-contract`.
- `next_candidate_id` is `candidate-broker-diagnostic-liveness-contract`.
- Markdown contains `## 비용 기준 요약`.

## Manifest Replay

Create a tab-separated manifest:

```text
execution-quality	automation/execution-quality-last-run	LAST_RUN.md
kis-smoke	automation/kis-smoke-last-run	LAST_RUN.md
rebalance-micro-gtaa	automation/rebalance-micro-gtaa-last-run	LAST_RUN.md
money-path	automation/money-path-last-run	LAST_RUN.md
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
released-work	automation/released-work-last-run	released_work.json
capital-path-readiness	automation/capital-path-readiness-last-run	capital_path_readiness.json
```

Then run:

```bash
uv run python scripts/execution_cost_basis_probe.py \
  --repo-root /tmp/sidecars \
  --manifest /tmp/sidecars/manifest.tsv \
  --format json
```

## Autonomous-Work Release Replay

After tasks are complete:

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '.released_work[] | select(.candidate_id=="candidate-execution-cost-basis-contract")'

uv run python scripts/autonomous_work_execution_probe.py \
  --repo-root . \
  --json \
  | jq '.selected_work.candidate_id'
```

Expected selected candidate after local released-work override:

```text
candidate-broker-diagnostic-liveness-contract
```

## Safety Check

The contract is read-only. It does not call KIS, place or retry orders, allocate capital, change live strategy, widen whitelist/caps, read secrets, modify kernel files, or use external paid services.
