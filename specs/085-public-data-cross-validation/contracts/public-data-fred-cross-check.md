# Contract: Public Data FRED Cross-Check

## Scope

This contract extends the research-only `collect-public-data` surface. It does not define a live trading input contract.

## Config Contract

`deploy/public-data.toml` may include:

```toml
[fred]
series = ["DGS2", "DGS10"]
min_rows = 1500
max_staleness_days = 7
user_agent = "httpx-default"
```

Allowed user-agent modes:

- `channel`: use the existing public-data channel user-agent.
- `httpx-default`: omit the channel override and allow the HTTP client default user-agent.

## Output Contract

When validation passes, output directory includes:

```text
fred/DGS2.csv
fred/DGS10.csv
```

Each CSV uses the existing series schema:

```csv
date,value
YYYY-MM-DD,4.40
```

`summary.json` includes item entries:

```json
{
  "kind": "fred",
  "id": "DGS10",
  "ok": true,
  "rows": 1500,
  "first_date": "YYYY-MM-DD",
  "last_date": "YYYY-MM-DD",
  "missing": 0,
  "issues": [],
  "published": "fred/DGS10.csv"
}
```

`summary.json` includes cross-check entries:

```json
{
  "pair": "treasury:UST10Y vs fred:DGS10",
  "kind": "levels",
  "status": "PASS",
  "overlap": 1500,
  "agree_pct": "100.00",
  "max_abs_diff": "0.000000",
  "detail": "..."
}
```

## Failure Contract

- Failed FRED item: `ok=false`, no `published`, issue message recorded.
- Missing FRED or Treasury side of a configured cross-check: `status=SKIPPED`.
- Divergent FRED-vs-Treasury levels: `status=FAIL` and `overall_ok=false`.
- No broker, KIS, order, live strategy, whitelist/caps, or secret surface may be touched by this contract.

## Released-work Marker

`released-work` consumes only explicit completion markers from fully checked Speckit work. When this spec is merged and post-merge handoff is refreshed, the completed candidate is:

```text
completed_candidate_id: candidate-facf2fa31834
```
