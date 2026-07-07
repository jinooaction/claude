# Quickstart: Broker Rejection Taxonomy Contract

## Local Fixture Run

```bash
uv run python scripts/broker_rejection_taxonomy_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/broker_rejection_taxonomy.json \
  --summary-out /tmp/broker_rejection_taxonomy.md
```

Expected:

- `overall_status` is `CONTRACT_READY` when current execution-quality evidence contains parsed KIS rejection codes.
- `completed_candidate_id` is `candidate-broker-rejection-taxonomy-contract`.
- `next_candidate_id` is `candidate-execution-cost-basis-contract`.
- Markdown contains `## 브로커 거부 분류`.

## Manifest Replay

Create a tab-separated manifest:

```text
execution-quality	automation/execution-quality-last-run	LAST_RUN.md
kis-smoke	automation/kis-smoke-last-run	LAST_RUN.md
rebalance-micro-gtaa	automation/rebalance-micro-gtaa-last-run	LAST_RUN.md
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
released-work	automation/released-work-last-run	released_work.json
capital-path-readiness	automation/capital-path-readiness-last-run	capital_path_readiness.json
```

Then run:

```bash
uv run python scripts/broker_rejection_taxonomy_probe.py \
  --repo-root /tmp/sidecars \
  --manifest /tmp/sidecars/manifest.tsv \
  --format json
```

## Autonomous-Work Release Replay

After tasks are complete:

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '.released_work[] | select(.candidate_id=="candidate-broker-rejection-taxonomy-contract")'

tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key branch file; do
  git show "origin/$branch:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root . \
  --json \
  | jq '.selected_work.candidate_id'
```

Expected selected candidate after local released-work override:

```text
candidate-execution-cost-basis-contract
```

## Safety Check

The contract is read-only. It does not call KIS, place or retry orders, allocate capital, change live strategy, widen whitelist/caps, read secrets, modify kernel files, or use external paid services.
