# Contract: Candidate History Support

## Manifest TSV

Producer:

```bash
uv run python scripts/candidate_history_support_probe.py --manifest
```

Format:

```text
key<TAB>portfolio_path<TAB>db_path<TAB>history_root
```

Rows must be stable and ordered:

1. `micro-gtaa`
2. `global-trend-wide`
3. `multi-asset-trend`

## Manifest JSON

Producer:

```bash
uv run python scripts/candidate_history_support_probe.py --json
```

Shape:

```json
{
  "schema_version": "1.0",
  "history_root": "/tmp/candidate_result_history",
  "datasets": [
    {
      "key": "micro-gtaa",
      "portfolio_path": "deploy/micro-gtaa-live-portfolio.toml",
      "db_path": "data/auto_invest.db",
      "history_root": "/tmp/candidate_result_history/micro-gtaa/hist"
    }
  ]
}
```

## Workflow Support Input

The candidate result executor workflow may:

- read existing server DB files through `bars-export`
- write temporary bars and ingested datasets under remote `/tmp`
- stream a compressed `/tmp` dataset archive back to the GitHub runner through the fixed `observe candidate-history <key>` gateway command
- extract the archive under `/tmp/candidate_result_history`

The workflow must not:

- use `scp`, raw remote `bash`, or direct remote `uv run auto-invest ...`
- call broker backfill commands
- place orders
- use `--mode live`
- edit live sentinel files
- edit whitelist/caps
- log secret values
- change source DBs or sidecar branches

## Candidate Command Contract

Candidate package commands may contain:

```bash
uv run auto-invest portfolio-walk-forward \
  --portfolio <portfolio> \
  --trailing-years 5 \
  --history-root <manifest history root> \
  --db data/candidate-factory/<candidate>.db \
  --halt-path data/candidate-factory/<candidate>.halt.flag \
  --json
```

Candidate package commands must not contain SSH, `VULTR_SSH`, `KIS_`, live mode, rebalance live requests, whitelist/caps edits, or sentinel writes.
