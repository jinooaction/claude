# Quickstart: Candidate History Support

## Inspect the manifest

```bash
uv run python scripts/candidate_history_support_probe.py --manifest
uv run python scripts/candidate_history_support_probe.py --json
```

Expected rows:

- `micro-gtaa` maps to `deploy/micro-gtaa-live-portfolio.toml`, `data/auto_invest.db`, `/tmp/candidate_result_history/micro-gtaa/hist`
- `global-trend-wide` maps to `deploy/global-trend-wide-portfolio.toml`, `data/forward_wide.db`, `/tmp/candidate_result_history/global-trend-wide/hist`
- `multi-asset-trend` maps to `deploy/multi-asset-trend-portfolio.toml`, `data/forward_multiasset.db`, `/tmp/candidate_result_history/multi-asset-trend/hist`

## Synthetic local smoke

Create enough local CSV history, ingest it to the same root shape, then run the generated candidate commands. This proves the new `--history-root` removes the previous `no ingested datasets` failure mode without requiring server secrets.

```bash
rm -rf /tmp/candidate_result_history
mkdir -p /tmp/candidate_result_history

uv run python scripts/candidate_history_support_probe.py --manifest \
  > /tmp/candidate_history_manifest.tsv

# Test implementation may generate synthetic CSVs under each row's bars directory,
# run ingest-history, then execute the current candidate package plan.
```

## Workflow validation

```bash
uv run pytest tests/unit/test_candidate_history_support.py -q
uv run pytest tests/unit/test_candidate_factory.py tests/unit/test_candidate_result_executor.py -q
uv run pytest tests/integration/test_candidate_result_executor_probe.py -q
```

Expected:

- candidate commands include `--history-root`
- workflow support input includes `bars-export -> ingest-history`
- candidate commands still contain no SSH/KIS/live/order/capital surfaces
- missing server data remains pending rather than pass
