# Contract: Quality, Redteam, and Handoff Harness

## Command: `uv run python scripts/agent_harness_probe.py --strict`

Expected behavior:
- Reads `.codex/harness/evaluation_tasks.toml`.
- Reads `.codex/harness/quality_tasks.toml`.
- Reads `.codex/harness/redteam_tasks.toml`.
- Runs local `HANDOFF.md` fact checks.
- Exits `0` only when all required controls pass.
- Exits non-zero in strict mode when any required static, quality, redteam, or handoff check fails.

JSON output with `--json` includes:

```json
{
  "status": "OK",
  "score": 14,
  "max_score": 14,
  "controls": [],
  "task_suite": {},
  "quality_suite": {},
  "redteam_suite": {},
  "handoff_facts": {}
}
```

## Command: `uv run python scripts/check_handoff_facts.py`

Expected behavior:
- Reads `HANDOFF.md` by default.
- Compares its summary table with local `origin/main`.
- Accepts optional expected validation strings for pytest, ruff, and open PR rows.
- Supports `--json`.
- Exits non-zero when required facts disagree.

## PR body requirement

Grade 2+ PR body must include:

- strict static/quality/redteam harness result
- handoff fact validation result
- existing full test and lint evidence
