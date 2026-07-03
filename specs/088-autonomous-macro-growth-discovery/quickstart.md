# Quickstart: Autonomous Macro Growth Discovery

## Focused Unit Tests

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py
```

Expected:

- Closed regular queue selects `candidate-macro-growth-discovery`.
- Released bootstrap candidate advances to `candidate-evolution-source-diversification`.
- Normal execution-ready candidates and approval-required candidates are not masked.

## Probe Reproduction

```bash
tmpdir="$(mktemp -d)"
cat > "$tmpdir/capital-path-readiness.md" <<'JSON'
{"priority_candidates":[{"candidate_id":"candidate-fd04772a23c5","domain_key":"live_readiness","status":"new","score":597}]}
JSON
cat > "$tmpdir/released-work.md" <<'JSON'
{"released_work":[{"candidate_id":"candidate-fd04772a23c5","status":"released","reason_ko":"이미 출시"}]}
JSON
cat > "$tmpdir/pipeline-liveness.md" <<'JSON'
{"overall":"OK","checks":[]}
JSON

uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --json \
  --now 2026-07-03T00:00:00Z \
  | jq '.selected_work.candidate_id'
```

Expected: `"candidate-macro-growth-discovery"`.

## Released-work Reproduction

After every checkbox in `tasks.md` is complete:

```bash
uv run python scripts/released_work_probe.py \
  --repo-root . \
  --run-id local-088 \
  --commit "$(git rev-parse HEAD)" \
  --json-out /tmp/released_work_088.json \
  --summary-out /tmp/released_work_088.md
jq '.released_work[] | select(.candidate_id=="candidate-macro-growth-discovery")' /tmp/released_work_088.json
```

Expected: one `released` entry sourced from `specs/088-autonomous-macro-growth-discovery/contracts/autonomous-macro-growth-discovery.md`.

## Full Verification

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
