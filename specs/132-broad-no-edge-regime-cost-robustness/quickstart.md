# Quickstart: Broad NO_EDGE Regime Cost Robustness

## Manifest

```bash
uv run python scripts/broad_no_edge_regime_cost_robustness_probe.py --manifest
```

Expected: eight rows for `regime-stratify`, `execution-quality`, `money-path`, `edge-autoarm`, `rebalance-paper-forward`, `released-work`, `evolution-ledger`, and `pipeline-liveness`.

## Local Sidecar Replay

Create a temporary evidence directory from automation refs:

```bash
tmpdir="$(mktemp -d)"
git show origin/automation/regime-stratify-last-run:LAST_RUN.md > "$tmpdir/regime-stratify.md"
git show origin/automation/execution-quality-last-run:LAST_RUN.md > "$tmpdir/execution-quality.md"
git show origin/automation/money-path-last-run:LAST_RUN.md > "$tmpdir/money-path.md"
git show origin/automation/edge-autoarm-last-run:LAST_RUN.md > "$tmpdir/edge-autoarm.md"
git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md > "$tmpdir/rebalance-paper-forward.md"
git show origin/automation/released-work-last-run:released_work.json > "$tmpdir/released-work.md"
git show origin/automation/autonomous-evolution-last-run:learning_ledger.json > "$tmpdir/evolution-ledger.md"
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md > "$tmpdir/pipeline-liveness.md"
uv run python scripts/broad_no_edge_regime_cost_robustness_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json
```

Expected current checkout result after tasks complete:

- `overall_status` is `CONTRACT_READY`.
- `completed_candidate_id` is `candidate-broad-no-edge-regime-cost-robustness-experiment`.
- `next_candidate_id` is `candidate-broad-no-edge-data-gap-audit`.
- `cost_stress_rows` has exactly 3 rows.
- `safety_boundary` includes `no orders` and `no capital allocation`.

## Focused Tests

```bash
uv run pytest \
  tests/unit/test_broad_no_edge_regime_cost_robustness.py \
  tests/integration/test_broad_no_edge_regime_cost_robustness_probe.py \
  tests/unit/test_autonomous_work_execution.py \
  -k 'regime_cost or broad_no_edge' \
  -q
```

## Full Validation

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
