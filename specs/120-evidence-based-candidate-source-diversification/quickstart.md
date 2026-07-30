# Quickstart: Evidence-Based Candidate Source Diversification

## Local Fixture Reproduction

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
uv run pytest tests/unit/test_candidate_factory.py tests/unit/test_candidate_result_executor.py -q
```

## Current Sidecar Reproduction

```bash
tmpdir="$(mktemp -d)"
git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'

git show origin/automation/released-work-last-run:released_work.json > "$tmpdir/released_work.json"
git show origin/automation/autonomous-evolution-last-run:candidate_backlog.json > "$tmpdir/candidate_backlog.json"
git show origin/automation/autonomous-evolution-last-run:learning_ledger.json > "$tmpdir/learning_ledger.json"
git show origin/automation/candidate-implementation-factory-last-run:candidate_factory.json > "$tmpdir/candidate_factory.json"
git show origin/automation/candidate-implementation-factory-last-run:candidate_packages.json > "$tmpdir/candidate_packages.json"
git show origin/automation/candidate-implementation-results:candidate_results.json > "$tmpdir/candidate_results.json"
git show origin/automation/money-path-last-run:LAST_RUN.md > "$tmpdir/money_path.md"
git show origin/automation/edge-autoarm-last-run:LAST_RUN.md > "$tmpdir/edge_autoarm.md"
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md > "$tmpdir/pipeline_liveness.md"
```

Run the autonomous work probe against the refreshed surfaces:

```bash
uv run python scripts/autonomous_work_execution_probe.py --help
```

Use the probe's repository workflow path if direct file flags are not available; the expected result is that released or suppressed candidates are not selected as active work when a fresh evidence-source-diversification packet can be built.

## Full Validation Before Merge

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
git diff --check
```
