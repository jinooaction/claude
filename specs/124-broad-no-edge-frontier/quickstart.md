# Quickstart: Broad NO_EDGE Frontier

1. Run the focused tests:

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

2. Confirm the parent candidate appears before release:

```bash
uv run python scripts/autonomous_work_execution_probe.py --help
```

3. Confirm full repository gates before merge:

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

The feature is complete only if broad no-edge parent release advances to a concrete no-live follow-up candidate and never authorizes live money movement.
