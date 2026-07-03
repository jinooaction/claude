# Quickstart: Learning Ledger Candidate Memory

## Focused Behavior

```bash
uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py
```

Expected:

- A candidate with an existing evidence-dependent ledger decision does not appear in `safe_high_leverage_work`.
- A candidate with an existing operator-review ledger decision remains in operator review output.
- Missing or malformed ledger input does not break candidate generation.

## Local Ledger Replay

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/evolution_loop_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
cat > "$tmpdir/learning_ledger.json" <<'JSON'
{"schema_version":"1.0","entries":[{"candidate_id":"candidate-fa66202bf496","decision":"evidence_dependent","reason_ko":"검증 장부가 이미 보류한 후보","next_recheck_condition":null,"created_at_utc":"2026-07-03T00:00:00Z"}]}
JSON
uv run python scripts/evolution_loop_probe.py \
  --evidence-dir "$tmpdir" \
  --ledger-json "$tmpdir/learning_ledger.json" \
  --json-out "$tmpdir/evolution_summary.json" \
  --ledger-out "$tmpdir/learning_ledger_out.json" \
  --candidate-backlog-out "$tmpdir/candidate_backlog.json" \
  --json
```

Expected: `candidate-fa66202bf496` is not in `safe_high_leverage_work`.

## Released-work Reproduction

Run only after `tasks.md` is complete:

```bash
uv run python scripts/released_work_probe.py \
  --repo-root . \
  --run-id local-087 \
  --commit "$(git rev-parse HEAD)" \
  --json-out /tmp/released_work_087.json \
  --summary-out /tmp/released_work_087.md
jq '.released_work[] | select(.candidate_id=="candidate-fa66202bf496")' /tmp/released_work_087.json
```

Expected: one `released` entry sourced from `specs/087-learning-ledger-candidate-memory/contracts/learning-ledger-candidate-memory.md`.

## Full Grade-2 Validation

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```

Before PR:

```bash
uv run python scripts/check_pr_quality_gate.py /tmp/codex-087-pr.md
```
