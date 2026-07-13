# Quickstart: Atomic Fill Ledger

## Focused Validation

```bash
uv run pytest tests/integration/test_fill_sync.py tests/integration/test_worker_fill_sync.py
```

Expected:

- duplicate planned fill does not move position cache
- injected position-update failure rolls back fill and audit writes
- existing fill sync scenarios remain green

## Full Validation

```bash
git diff --check
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

## Safety Review

Confirm the diff does not touch:

- live sentinels
- capital settings
- whitelist or caps
- loss budget
- `.specify/memory/constitution.md`
- `.specify/memory/kernel.toml`
- real broker workflow dispatch

## Expected Operational State

This feature changes only local accounting safety. It does not arm live trading. Current money path remains `PREVIEW_ONLY`.
