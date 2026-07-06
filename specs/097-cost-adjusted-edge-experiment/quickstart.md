# Quickstart: Cost-Adjusted Edge Experiment

## Focused tests

```bash
uv run pytest tests/unit/test_cost_adjusted_edge_experiment.py tests/integration/test_cost_adjusted_edge_experiment_probe.py
```

## Probe manifest

```bash
uv run python scripts/cost_adjusted_edge_experiment_probe.py --manifest
```

## Local sidecar replay

Collect current sidecar snapshots into a temporary directory as `<key>.md` files:

```text
rebalance-paper-forward.md
execution-quality.md
money-path.md
released-work.md
evolution-ledger.md
pipeline-liveness.md
```

Then run:

```bash
uv run python scripts/cost_adjusted_edge_experiment_probe.py \
  --sidecar-dir .verify/cost-adjusted-sidecars \
  --repo-root . \
  --json \
  --json-out .verify/cost-adjusted-edge-experiment.json \
  --summary-out .verify/cost-adjusted-edge-experiment-LAST_RUN.md \
  --now 2026-07-06T00:00:00Z \
  --run-id local \
  --commit "$(git rev-parse HEAD)"
```

Expected current replay: `overall_status=OBSERVATION_WAIT`, `cost-basis-completeness=WAIT`, `released-work-closure=PASS`, and no live-money action.

## Release replay

After implementation, verify released-work and autonomous-work no longer choose this candidate:

```bash
uv run python scripts/released_work_probe.py --repo-root . --json
uv run python scripts/autonomous_work_probe.py --repo-root . --json
```

## Full validation

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

