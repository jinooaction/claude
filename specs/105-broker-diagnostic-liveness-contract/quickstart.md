# Quickstart: Broker Diagnostic Liveness Contract

## Local Fixture Run

```bash
uv run python scripts/broker_diagnostic_liveness_probe.py \
  --repo-root . \
  --format json \
  --json-out /tmp/broker_diagnostic_liveness.json \
  --summary-out /tmp/broker_diagnostic_liveness.md
```

Expected for current sidecar evidence:

- `overall_status` is `CONTRACT_READY` when KIS smoke, execution-quality broker smoke, and pipeline-liveness are healthy.
- `diagnostic_summary.diagnostic_state` is `BROKER_DIAGNOSTIC_LIVE`.
- `completed_candidate_id` is `candidate-broker-diagnostic-liveness-contract`.
- `next_candidate_id` is `candidate-agent-ops-frontier-map`.
- Markdown contains `## 브로커 진단 생존성 요약`.

## Manifest Replay

Create a tab-separated manifest:

```text
kis-smoke	automation/kis-smoke-last-run	LAST_RUN.md
execution-quality	automation/execution-quality-last-run	LAST_RUN.md
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
released-work	automation/released-work-last-run	released_work.json
capital-path-readiness	automation/capital-path-readiness-last-run	capital_path_readiness.json
```

Then run:

```bash
uv run python scripts/broker_diagnostic_liveness_probe.py \
  --repo-root /tmp/sidecars \
  --manifest /tmp/sidecars/manifest.tsv \
  --format json
```

## Autonomous-Work Release Replay

After tasks are complete:

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '.released_work[] | select(.candidate_id=="candidate-broker-diagnostic-liveness-contract")'

uv run python scripts/autonomous_work_execution_probe.py \
  --repo-root . \
  --json \
  | jq '.selected_work.candidate_id'
```

Expected selected candidate after local released-work override:

```text
candidate-agent-ops-frontier-map
```

## Safety Check

The contract is read-only. It does not call KIS, place or retry orders, allocate capital, change live strategy, widen whitelist/caps, read secrets, modify kernel files, or use external paid services.
