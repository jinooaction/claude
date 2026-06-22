# Quickstart: Agent Quality Redteam Harness

Run the combined harness:

```bash
uv run python scripts/agent_harness_probe.py --strict
```

Run the handoff fact checker directly:

```bash
uv run python scripts/check_handoff_facts.py \
  --expect-pytest "2205 passed, 4 skipped" \
  --expect-ruff "All checks passed"
```

Validate the PR template:

```bash
python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md
```

Expected final validation:

```bash
uv run pytest
uv run ruff check src tests
```
