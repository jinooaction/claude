# Quickstart: Candidate Result Executor

```bash
tmpdir="$(mktemp -d)"

git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'
git show origin/automation/candidate-implementation-factory-last-run:candidate_packages.json \
  > "$tmpdir/candidate_packages.json"

uv run python scripts/candidate_result_executor_probe.py \
  --package-plan "$tmpdir/candidate_packages.json" \
  --summary-out "$tmpdir/LAST_RUN.md" \
  --json-out "$tmpdir/candidate_result_executor.json" \
  --results-out "$tmpdir/candidate_results.json" \
  --run-id local

cat "$tmpdir/LAST_RUN.md"
jq '.results | length' "$tmpdir/candidate_results.json"
```

Validation:

```bash
uv run pytest tests/unit/test_candidate_result_executor.py \
  tests/integration/test_candidate_result_executor_probe.py
uv run ruff check src tests scripts/candidate_result_executor_probe.py
```
