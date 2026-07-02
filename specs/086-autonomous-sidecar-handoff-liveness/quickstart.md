# Quickstart: Autonomous Sidecar Handoff Liveness Closure

## Focused Behavior

```bash
uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py
```

Expected:

- Satisfied `pipeline-liveness` plus `handoff` evidence marks `candidate-88a7e7f07361` as `released`.
- Missing `autonomous-evolution` liveness evidence leaves the candidate actionable.

## Released-work Reproduction

```bash
uv run python scripts/released_work_probe.py \
  --repo-root . \
  --run-id local-086 \
  --commit "$(git rev-parse HEAD)" \
  --json-out /tmp/released_work_086.json \
  --summary-out /tmp/released_work_086.md
jq '.released_work[] | select(.candidate_id=="candidate-88a7e7f07361")' /tmp/released_work_086.json
```

Expected: one `released` entry sourced from `specs/086-autonomous-sidecar-handoff-liveness/contracts/agent-ops-liveness-closure.md`.

## Downstream Stale-Sidecar Reproduction

Use stale promotion/factory inputs with current released-work evidence. Expected result:

- promotion stage for `candidate-88a7e7f07361`: `DISCARD`
- factory package output contains no `candidate-88a7e7f07361`

## Full Grade-2 Validation

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

Before PR:

```bash
uv run python scripts/check_pr_quality_gate.py /tmp/codex-086-pr.md
```
