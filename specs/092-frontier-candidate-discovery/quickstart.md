# Quickstart: Frontier Candidate Discovery

## 1. Focused unit tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

Expected:

- All released macro candidates advance to `candidate-autonomous-frontier-discovery`.
- Regular execution-ready candidates still outrank frontier discovery.
- Operator-approval candidates are not masked.

## 2. Latest sidecar replay

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
  | jq '.selected_work | {candidate_id, status, risk_grade, safety_impact}'
```

Expected before this spec's completion marker is consumed:

```json
{
  "candidate_id": "candidate-autonomous-frontier-discovery",
  "status": "EXECUTION_READY",
  "risk_grade": 2,
  "safety_impact": []
}
```

## 3. Released-work closure reproduction

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq -r '.released_work[] | select(.candidate_id=="candidate-autonomous-frontier-discovery")'
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
