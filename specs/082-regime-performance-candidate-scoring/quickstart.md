# Quickstart: 레짐·성과 후보 점수화

## Focused validation

```bash
uv run pytest \
  tests/unit/test_evolution_loop.py \
  tests/integration/test_evolution_loop_probe.py \
  -q
```

## Local sidecar smoke

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/evolution_loop_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/${ref}:${file}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done

uv run python scripts/evolution_loop_probe.py \
  --evidence-dir "${tmpdir}" \
  --json \
  | jq '.candidates[] | select(.candidate_id=="candidate-e481b0309206") | {evidence_refs, composite_score, evidence_dependency, status}'
```

Expected:

- `evidence_refs` contains `regime-stratify`, `public-data`, and `promote-readiness`.
- Missing or stale `promote-readiness` lowers confidence and marks sidecar freshness dependency.
- No orders, broker calls, SSH, KIS secrets, capital, live strategy, whitelist/caps changes occur.

## Full validation before PR

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_pr_quality_gate.py /tmp/pr-082-body.md
```
