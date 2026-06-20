# Quickstart: Agent Harness Evaluation

## Run The Harness Probe

```bash
uv run python scripts/agent_harness_probe.py --strict
```

Expected result: text output with overall `OK` and exit code 0.

## Run JSON Output

```bash
uv run python scripts/agent_harness_probe.py --json --strict
```

Expected result: JSON output whose `status` is `OK`.

## Validate The PR Template

```bash
python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md
```

Expected result: `pr-quality-gate-ok`.

## Validate A Filled PR Body

For a grade 2 operating change, the PR body must include:

```markdown
## 하네스 검증

- 하네스 평가: `uv run python scripts/agent_harness_probe.py --strict` → 통과
```

Then run:

```bash
python3 scripts/check_pr_quality_gate.py /tmp/pr_body.md
```

Expected result: `pr-quality-gate-ok`.
