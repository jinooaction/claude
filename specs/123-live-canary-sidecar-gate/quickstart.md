# Quickstart: Live Canary Sidecar Gate

## Local Focused Checks

```bash
uv run pytest tests/unit/test_live_canary_workflow.py tests/unit/test_security_workflow_hardening.py tests/unit/test_workflow_backfill_depth.py tests/unit/test_workflow_nav_capital_basis.py -q
uv run pytest tests/unit/test_ssh_boundary_repair.py tests/unit/test_observation_gateway_workflows.py -q
bash -n deploy/repair-ssh-boundary.sh deploy/observe-on-instance.sh
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/rebalance-live-canary.yml"); puts "yaml-ok"'
uv run pytest tests/unit/test_pipeline_liveness.py tests/integration/test_pipeline_liveness_probe.py tests/unit/test_capital_path_readiness.py tests/integration/test_capital_path_readiness_probe.py -q
```

## Full Pre-Merge Checks

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
git diff --check
```

## PR Quality Gate

```bash
uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md
uv run python scripts/check_pr_quality_gate.py <pr-body-file>
```

## Post-Merge Sidecar Checks

```bash
gh workflow run rebalance-live-canary.yml --repo jinooaction/claude --ref main
gh run watch <run_id> --repo jinooaction/claude --exit-status
git fetch origin automation/rebalance-live-canary-last-run
git show origin/automation/rebalance-live-canary-last-run:LAST_RUN.md
```

Expected result while `armed=false`: the sidecar timestamp is fresh, `LIVE 스텝` says `preview-job-skipped`, the text says real orders are owned by the production-gated job, and no production real-order job is approved or executed.

The backfill, preview, and live-track measurement sections should not contain `refused command`. If they briefly refuse right after merge, rerun after deploy-on-merge refreshes the root-owned gateway/helper.

Then refresh pipeline liveness:

```bash
gh workflow run pipeline-liveness.yml --repo jinooaction/claude --ref main
gh run watch <run_id> --repo jinooaction/claude --exit-status
git fetch origin automation/pipeline-liveness-last-run
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md
```

Expected result: `rebalance-live-canary` is no longer late unless a new, unrelated freshness threshold has failed.
