# Quickstart: Capital Path Readiness Loop

## Local latest-sidecar smoke

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/capital_path_readiness_probe.py --manifest |
while IFS=$'\t' read -r key branch filename; do
  git show "origin/${branch}:${filename}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done
uv run python scripts/capital_path_readiness_probe.py \
  --evidence-dir "${tmpdir}" \
  --json-out /tmp/capital_path_readiness.json \
  --summary-out /tmp/capital_path_readiness.md \
  --json
cat /tmp/capital_path_readiness.md
```

Expected current-shape result:

- `readiness_state` is not `CAPITAL_ARMABLE` while money-path is accumulating edge or preview-only.
- `live_money_status` reflects money-path `live_money_state.status`.
- rejected strategy/portfolio candidates are listed under `suppressed_candidates`.

## Focused tests

```bash
uv run pytest tests/unit/test_capital_path_readiness.py tests/integration/test_capital_path_readiness_probe.py -q
uv run ruff check src/auto_invest/analytics/capital_path_readiness.py scripts/capital_path_readiness_probe.py tests/unit/test_capital_path_readiness.py tests/integration/test_capital_path_readiness_probe.py
```
