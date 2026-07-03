# Quickstart: Autonomous Growth Objective Calibration

## 1. Focused unit tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

Expected:

- Objective calibration appears in `to_dict()`.
- `selected_candidate_id` matches `selected_work.candidate_id`.
- Safety-impact candidates remain `OPERATOR_APPROVAL_REQUIRED` and receive a lower safety margin.

## 2. Probe JSON and Markdown output

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root . \
  --json \
  --json-out "$tmpdir/autonomous_work_execution.json" \
  --summary-out "$tmpdir/LAST_RUN.md" \
  | jq '.objective_calibration | {selected_candidate_id, exploration_budget, learning_metrics}'
rg -n "목적 함수 보정|candidate-autonomous-growth-objective-calibration" "$tmpdir/LAST_RUN.md"
```

Expected:

- JSON contains `objective_calibration`.
- Markdown contains `## 목적 함수 보정`.
- The selected candidate is explained with component scores.

## 3. Released-work closure reproduction

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq -r '.released_work[] | select(.candidate_id=="candidate-autonomous-growth-objective-calibration")'
```

Expected after all implementation tasks are checked:

- The candidate appears as `released`.

## 4. Full validation

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

Expected:

- All checks pass before PR merge.
