# Quickstart: 자율 루프 품질 폐쇄

## Focused verification

```bash
uv run pytest \
  tests/unit/test_autonomous_work_execution.py \
  tests/unit/test_money_gate_alignment.py \
  tests/unit/test_pipeline_liveness.py \
  tests/integration/test_autonomous_work_execution_probe.py \
  tests/integration/test_money_gate_alignment_probe.py \
  tests/integration/test_pipeline_liveness_probe.py -q
```

## Local sidecar smoke

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest > "$tmpdir/awe.tsv"
while IFS=$'\t' read -r key branch filename; do
  git show "origin/${branch}:${filename}" > "$tmpdir/${key}.md" 2>/dev/null || true
done < "$tmpdir/awe.tsv"
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root "$PWD" \
  --json | jq '.selected_work | {candidate_id, autonomy_level, start_guidance_ko, completion_gates}'
```

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/money_gate_alignment_probe.py --manifest > "$tmpdir/mga.tsv"
while IFS=$'\t' read -r key branch filename; do
  git show "origin/${branch}:${filename}" > "$tmpdir/${key}.md" 2>/dev/null || true
done < "$tmpdir/mga.tsv"
uv run python scripts/money_gate_alignment_probe.py \
  --evidence-dir "$tmpdir" \
  --json | jq '.alignment_issues[] | select(.severity=="SNAPSHOT_SKEW")'
```

## Full gate before merge

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md
```
