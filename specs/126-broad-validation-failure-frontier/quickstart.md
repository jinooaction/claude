# Quickstart: Broad Validation Failure Frontier

## Focused Tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

## Current Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
while IFS=$'\t' read -r key branch file_name; do
  git show "origin/$branch:$file_name" > "$tmpdir/$key.md"
done < <(uv run python scripts/autonomous_work_execution_probe.py --manifest)

uv run python scripts/autonomous_work_execution_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root "$PWD" \
  --json \
  --now 2026-08-11T12:00:00Z
```

Expected after this spec is scanned:

- `selected_work.candidate_id == "candidate-broad-validation-failure-command-replay-contract"`
- `broad_validation_failure_frontier_map[0].coverage_status == "open"`
- `broad_validation_failure_frontier_map[0].package_count == 2`

## Completion Gates

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
