# Quickstart: Money Path State Guard

## Local sidecar reproduction

```bash
tmpdir=$(mktemp -d)
git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'
uv run python scripts/money_path_probe.py --manifest > "$tmpdir/manifest.tsv"
while IFS=$'\t' read -r key branch filename; do
  git show "origin/${branch}:${filename}" > "$tmpdir/${key}.md" 2>/dev/null || true
done < "$tmpdir/manifest.tsv"
uv run python scripts/money_path_probe.py --sidecar-dir "$tmpdir"
uv run python scripts/money_path_probe.py --sidecar-dir "$tmpdir" --json
```

Expected current-state behavior:
- The text output starts with `실제 돈 최상위 상태`.
- With `automation/rebalance-micro-gtaa.request` currently `armed:true`, the status says `실제 돈 경로 무장`.
- It also says live order submission still requires non-push event, regular session, cash preflight, breaker, caps, and whitelist.

## Focused tests

```bash
uv run pytest tests/unit/test_money_path.py tests/integration/test_money_path_probe.py tests/unit/test_micro_gtaa_canary.py
uv run ruff check src tests
```

## Full validation before merge

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
