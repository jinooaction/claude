# Quickstart: 공개 데이터 교차 검증 확장

## Focused Local Validation

```bash
uv run pytest tests/unit/test_public_data.py tests/unit/test_collect_public_data_workflow.py
```

Expected:

- Official-source happy path publishes 11 items.
- Cross-check status list includes the existing 3 checks plus 2 FRED checks.
- FRED requests use the configured `httpx-default` user-agent mode.
- Trading workflows still do not consume public-data.

## Dry-Run Collection

```bash
tmpdir="$(mktemp -d)"
uv run auto-invest collect-public-data --config deploy/public-data.toml --out-dir "$tmpdir" --json
jq '.published, .cross_checks' "$tmpdir/summary.json"
```

Expected:

- If all current public sources are reachable, `published` is 11.
- `treasury:UST2Y vs fred:DGS2` and `treasury:UST10Y vs fred:DGS10` appear in `cross_checks`.
- Any temporary FRED failure is item-level fail-soft and visible in `summary.json`.

## Full Completion Gates

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
