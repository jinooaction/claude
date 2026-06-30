# Quickstart: Candidate Evidence Diagnostics

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
  --run-id local \
  --timeout-seconds 60

jq '.diagnostic_counts' "$tmpdir/candidate_result_executor.json"
jq '.results[] | select(.status=="pending") | {candidate_id, package_kind, diagnostics, next_actions}' \
  "$tmpdir/candidate_results.json"
cat "$tmpdir/LAST_RUN.md"
```

Factory propagation check:

```bash
uv run python scripts/candidate_factory_probe.py \
  --candidate-backlog tests/fixtures/candidate_factory/fresh/candidate_backlog.json \
  --promotion-summary tests/fixtures/candidate_factory/fresh/promotion_summary.json \
  --result-evidence "$tmpdir/candidate_results.json" \
  --summary-out "$tmpdir/factory.md" \
  --json-out "$tmpdir/factory.json" \
  --enriched-backlog-out "$tmpdir/candidate_backlog.enriched.json" \
  --package-plan-out "$tmpdir/candidate_packages.next.json"

jq '.candidates[].promotion_evidence | select(.factory_diagnostics)' \
  "$tmpdir/candidate_backlog.enriched.json"
```

Validation:

```bash
uv run pytest tests/unit/test_candidate_result_executor.py \
  tests/unit/test_candidate_factory.py \
  tests/integration/test_candidate_result_executor_probe.py
uv run ruff check src tests scripts/candidate_result_executor_probe.py
```
