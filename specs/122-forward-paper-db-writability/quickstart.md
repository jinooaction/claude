# Quickstart: Forward Paper DB Writability

## Local Focused Checks

```bash
bash -n deploy/observe-on-instance.sh
uv run pytest tests/unit/test_forward_workflow_halt_isolation.py tests/unit/test_ssh_boundary_repair.py
```

## Full Pre-Merge Checks

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
git diff --check
```

## Post-Merge Sidecar Checks

```bash
gh workflow run rebalance-paper-forward.yml --repo jinooaction/claude --ref main
gh run watch <run_id> --repo jinooaction/claude --exit-status
git fetch origin automation/rebalance-paper-forward-last-run
git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md
```

Expected result: paper prep no longer fails with `OperationalError: attempt to write a readonly database`. If an external KIS/data failure remains, report it separately; do not treat it as a writability failure.
