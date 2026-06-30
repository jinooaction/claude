# Contract: Candidate Result Executor

## CLI

```bash
uv run auto-invest candidate-results \
  --package-plan /tmp/candidate_packages.json \
  --summary-out /tmp/LAST_RUN.md \
  --json-out /tmp/candidate_result_executor.json \
  --results-out /tmp/candidate_results.json \
  --run-id local
```

## Input: `candidate_packages.json`

```json
{
  "schema_version": "1.0",
  "packages": [
    {
      "package_id": "pkg-example",
      "candidate_id": "candidate-example",
      "package_kind": "strategy_backtest",
      "status": "ready",
      "commands": ["uv run auto-invest portfolio-walk-forward ..."],
      "produces_evidence": ["historical_backtest", "recent_oos", "walk_forward"]
    }
  ]
}
```

## Output: `candidate_results.json`

```json
{
  "schema_version": "1.0",
  "results": [
    {
      "candidate_id": "candidate-example",
      "package_id": "pkg-example",
      "package_kind": "strategy_backtest",
      "status": "pending",
      "historical_backtest": "pending",
      "recent_oos": "pending",
      "walk_forward": "pending",
      "source_ref": "candidate-result-executor:pkg-example",
      "block_reason_ko": "검증 출력이 아직 세 필수 증거를 모두 통과하지 못했다."
    }
  ]
}
```

## Safety Contract

- The executor must not call broker APIs.
- The executor must not pass `--mode live` or `--confirm-live`.
- The executor must not edit live sentinels, whitelist, caps, or capital ladder files.
- The executor must publish sidecar files only.
