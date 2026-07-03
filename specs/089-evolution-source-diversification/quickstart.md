# Quickstart: Evolution Source Diversification

## Focused Tests

```bash
uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py -q
```

Expected:

- Closed static candidate set produces an evidence-derived source diversification candidate.
- Existing safe static candidates remain ahead of synthesized candidates.
- Probe output writes the synthesized candidate to `candidate_backlog.json`.

## Local Sidecar Reproduction

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/evolution_loop_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
git show origin/automation/autonomous-evolution-last-run:learning_ledger.json > "$tmpdir/learning_ledger.json" 2>/dev/null || true
uv run python scripts/evolution_loop_probe.py \
  --evidence-dir "$tmpdir" \
  --ledger-json "$tmpdir/learning_ledger.json" \
  --candidate-backlog-out "$tmpdir/candidate_backlog.json" \
  --json | jq '.safe_high_leverage_work, [.candidates[] | select(.domain_key=="agent_ops")]'
```

Expected:

- The candidate backlog contains `증거 기반 후보 소스 다변화`.
- The candidate is read-only, risk grade 2, and has no safety impact.

## Release Marker Verification

After all implementation tasks are checked complete:

```bash
uv run python scripts/released_work_probe.py \
  --repo-root . \
  --run-id local-089 \
  --commit "$(git rev-parse HEAD)" \
  --json-out /tmp/released_work_089.json \
  --summary-out /tmp/released_work_089.md
jq '.released_work[] | select(.candidate_id=="candidate-evolution-source-diversification")' /tmp/released_work_089.json
```
