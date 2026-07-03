# Quickstart: Source Diversification Candidate Closure

## 1. Focused regression

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

Expected:

- A released `candidate-source-diversification-sidecar-bottleneck` is not selected as executable work.
- The next macro candidate is `candidate-autonomous-growth-objective-calibration`.

## 2. Released-work reproduction

```bash
uv run python scripts/released_work_probe.py \
  --repo-root . \
  --run-id local-090 \
  --commit "$(git rev-parse HEAD)" \
  --json-out /tmp/released_work_090.json \
  --summary-out /tmp/released_work_090.md

jq '.released_work[] | select(.candidate_id=="candidate-source-diversification-sidecar-bottleneck")' \
  /tmp/released_work_090.json
```

Expected: one released-work entry from `specs/090-source-diversification-candidate-closure`.

## 3. Latest sidecar replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/${ref}:${file}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done

uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root . \
  --run-id local-090 \
  --commit "$(git rev-parse HEAD)" \
  --json | jq '.selected_work | {candidate_id, status, risk_grade, safety_impact}'

rm -rf "$tmpdir"
```

Expected:

```json
{
  "candidate_id": "candidate-autonomous-growth-objective-calibration",
  "status": "EXECUTION_READY",
  "risk_grade": 2,
  "safety_impact": []
}
```

## 4. Full closure checks

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
