# Quickstart: 주문 거부·체결 품질 손익 관측

## Local probe

```bash
tmpdir="$(mktemp -d)"
git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'
git show origin/automation/rebalance-micro-gtaa-last-run:opportunity_monitor.json > "$tmpdir/opportunity-monitor.md"
git show origin/automation/rebalance-micro-gtaa-last-run:opportunity_history.json > "$tmpdir/opportunity-history.md"
git show origin/automation/rebalance-micro-gtaa-last-run:LAST_RUN.md > "$tmpdir/rebalance-micro-gtaa.md"
git show origin/automation/kis-smoke-last-run:LAST_RUN.md > "$tmpdir/kis-smoke.md"
uv run python scripts/execution_quality_probe.py \
  --evidence-dir "$tmpdir" \
  --json-out "$tmpdir/execution_quality.json" \
  --summary-out "$tmpdir/LAST_RUN.md" \
  --json
```

Expected:

- `execution_quality.json` contains monitor verdict, broker rejection summary, smoke summary, and safety invariants.
- `LAST_RUN.md` says the report is read-only and does not place orders or change capital.

## Workflow sidecar

```bash
git show origin/automation/execution-quality-last-run:execution_quality.json
git show origin/automation/execution-quality-last-run:LAST_RUN.md
```

Expected:

- Both files exist after the workflow runs.
- Missing sidecar is a liveness visibility issue, not a live trading action.

## Focused tests

```bash
uv run pytest \
  tests/unit/test_execution_quality.py \
  tests/integration/test_execution_quality_probe.py \
  tests/unit/test_evolution_loop.py \
  tests/integration/test_evolution_loop_probe.py \
  tests/unit/test_pipeline_liveness.py \
  tests/integration/test_pipeline_liveness_probe.py
```

## Full gates

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
