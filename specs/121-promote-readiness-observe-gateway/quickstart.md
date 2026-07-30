# Quickstart: Promote Readiness Observe Gateway

## Focused Validation

```bash
uv run pytest tests/unit/test_observation_gateway_workflows.py tests/unit/test_ssh_boundary_repair.py tests/unit/test_spec_026_readiness.py -q
bash -n deploy/repair-ssh-boundary.sh
bash -n deploy/observe-on-instance.sh
```

## Current Sidecar Check

```bash
git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'
git show origin/automation/promote-readiness-last-run:LAST_RUN.md
```

Before this feature is deployed on the server, a stale sidecar may show `ssh_exit=126` and `refused command`. After the server has the updated gateway/helper, the sidecar should publish either READY true with exit 0 or READY false with exit 1.

## Full Validation Before Merge

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
git diff --check
```

## Post-Merge Truth Check

```bash
git fetch origin '+refs/heads/main:refs/remotes/origin/main' '+refs/heads/automation/*:refs/remotes/origin/automation/*'
git log --oneline -1 origin/main
git show origin/automation/promote-readiness-last-run:LAST_RUN.md
```

If the promotion readiness workflow is not triggered by the handoff-only merge, report the latest sidecar commit separately from the latest main commit.
