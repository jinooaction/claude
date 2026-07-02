# Quickstart: Stale Evidence Failure Separation

## Focused Validation

```bash
uv run pytest tests/unit/test_capital_path_readiness.py tests/integration/test_capital_path_readiness_probe.py
```

## Probe Smoke

```bash
uv run python scripts/capital_path_readiness_probe.py --manifest
uv run python scripts/capital_path_readiness_probe.py --evidence-dir /tmp/capital_path_sidecars --json
```

## Full Validation Before Merge

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
