# Quickstart: Worktree Concurrency Liveness Contract

## 1. Capture optional local guard observation

```bash
python3 scripts/local_concurrency_guard.py --mode check > /tmp/local_concurrency_guard_check.txt
```

`WARN` is acceptable when it points to `--mode isolate`; it proves the guard detected a local concurrency risk. The contract fails only on guard failure text or broken static/synthetic behavior.

## 2. Run the probe

```bash
uv run python scripts/worktree_concurrency_liveness_probe.py \
  --repo-root . \
  --guard-check /tmp/local_concurrency_guard_check.txt \
  --format json \
  --json-out /tmp/worktree_concurrency_liveness.json \
  --summary-out /tmp/worktree_concurrency_liveness.md
```

Expected before release:

- `overall_status` may be `OBSERVATION_WAIT` if released-work has not consumed this candidate yet.
- Static hook gates and synthetic guard behavior gates are `PASS`.

## 3. Confirm released-work consumes the marker

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '[.released_work[] | select(.candidate_id=="candidate-worktree-concurrency-liveness-contract")]'
```

Expected after tasks are complete:

- One released entry for `candidate-worktree-concurrency-liveness-contract`.

## 4. Confirm autonomous-work advances

```bash
uv run python scripts/autonomous_work_execution_probe.py --repo-root . --json \
  | jq '.selected_work.candidate_id'
```

Expected after this candidate is released:

```text
candidate-agent-harness-regression-liveness-contract
```

## 5. Full verification before merge

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
