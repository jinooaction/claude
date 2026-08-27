# Quickstart: Parallel Regime Edge Challenger

## Preregistration Integrity

```bash
python -m json.tool specs/171-parallel-regime-edge-challenger/contracts/preregistered-challenger.json >/dev/null
git show HEAD:specs/171-parallel-regime-edge-challenger/contracts/preregistered-challenger.json
```

The second command must succeed from the preregistration commit before the production-data probe runs.

## Focused Verification

```bash
uv run pytest \
  tests/unit/test_regime_adaptive_challenger.py \
  tests/integration/test_regime_adaptive_challenger_probe.py \
  tests/unit/test_forward_edge_autoarm_workflow.py
uv run ruff check src tests scripts/regime_adaptive_challenger_probe.py
```

## No-Order Research Probe

```bash
uv run python scripts/regime_adaptive_challenger_probe.py \
  --contract specs/171-parallel-regime-edge-challenger/contracts/preregistered-challenger.json \
  --output /tmp/regime-edge-result.json \
  --markdown-output specs/171-parallel-regime-edge-challenger/production-result.md
```

The result must contain `promotion_allowed=false`, `orders_submitted=0`, and `capital_changed=false`
regardless of verdict.

## Full Verification

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```
