# Quickstart: Macro Candidate Map Regenerator

## Focused Unit Tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

Expected:

- Existing macro/frontier tests continue to pass.
- When `candidate-macro-candidate-map-regenerator` is not released, it is selected after frontier discovery is released.
- When `candidate-macro-candidate-map-regenerator` is released, `candidate-investment-edge-frontier-map` is selected.

## Probe Tests

```bash
uv run pytest tests/integration/test_autonomous_work_execution_probe.py -q
```

Expected:

- JSON output includes `macro_candidate_map`.
- Markdown output includes `## 거시 후보 지도`.

## Local Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py --evidence-dir "$tmpdir" --repo-root . --json \
  | jq '{candidate_id:.selected_work.candidate_id,status:.selected_work.status,macro_candidate_map:.macro_candidate_map}'
```

Expected after this spec is implemented locally:

- Before released-work sees the spec 093 marker, `candidate-macro-candidate-map-regenerator` can be selected.
- After released-work sees the spec 093 marker, the next regenerated frontier candidate can be selected.

## Full Gate

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
