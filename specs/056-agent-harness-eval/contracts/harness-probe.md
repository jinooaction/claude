# Contract: Agent Harness Probe

## Command

```bash
uv run python scripts/agent_harness_probe.py [--repo PATH] [--json] [--strict]
```

## Behavior

- Reads only files under the target repository.
- Uses no network.
- Reads no secrets or `.env` files.
- Places no orders and does not execute deployment commands.
- Prints text by default and JSON with `--json`.
- Returns `0` when all required controls pass.
- Returns `1` in `--strict` mode when one or more required controls fail.
- Returns `2` for invalid arguments or unreadable task-suite data.

## JSON Shape

```json
{
  "status": "OK",
  "score": 11,
  "max_score": 11,
  "controls": [
    {
      "id": "codex_hooks_order",
      "title": "SessionStart hook order",
      "severity": "required",
      "status": "PASS",
      "evidence": ".codex/hooks.json",
      "message": "local concurrency guard runs before git ground truth"
    }
  ],
  "task_suite": {
    "status": "PASS",
    "path": ".codex/harness/evaluation_tasks.toml",
    "task_count": 12,
    "risk_grades": [0, 1, 2, 3, 4],
    "control_categories": ["context_truth", "concurrency"]
  }
}
```

## Failure Contract

When a required control fails, the matching control entry must contain:

- `status = "FAIL"`
- a non-empty `evidence` field naming the missing or invalid file
- a `message` that explains the missing condition
