# Contract: Candidate Evidence Diagnostics

## Input

Same input as spec 071:

```json
{
  "schema_version": "1.0",
  "packages": [
    {
      "package_id": "pkg-example",
      "candidate_id": "candidate-example",
      "package_kind": "strategy_backtest",
      "status": "ready",
      "commands": ["uv run auto-invest portfolio-walk-forward ..."]
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
      "block_reason_ko": "검증 명령이 실행됐지만 데이터 또는 환경 부족으로 실패했다.",
      "diagnostics": [
        {
          "code": "data_history_missing",
          "severity": "warning",
          "retryable": true,
          "summary_ko": "과거 가격 데이터가 준비되지 않았다.",
          "evidence_source": "command",
          "next_actions": [
            {
              "action_code": "prepare_history_dataset",
              "summary_ko": "안전한 데이터 수집 또는 ingest-history 실행 경로를 준비한다.",
              "owner": "automation",
              "safe_to_auto_run": true
            }
          ],
          "details": {
            "exit_code": 64,
            "stderr_excerpt": "no ingested datasets; run `auto-invest ingest-history`"
          }
        }
      ],
      "next_actions": [
        {
          "action_code": "prepare_history_dataset",
          "summary_ko": "안전한 데이터 수집 또는 ingest-history 실행 경로를 준비한다.",
          "owner": "automation",
          "safe_to_auto_run": true
        }
      ],
      "retryable": true
    }
  ]
}
```

## Output: Candidate Factory `promotion_evidence`

```json
{
  "factory_package_id": "pkg-example",
  "factory_kind": "strategy_backtest",
  "factory_status": "pending",
  "factory_source": "candidate-implementation-factory",
  "factory_block_reason_ko": "검증 결과가 아직 세 필수 증거를 모두 통과하지 못했다.",
  "historical_backtest": "pending",
  "recent_oos": "pending",
  "walk_forward": "pending",
  "factory_diagnostics": [
    {
      "code": "data_history_missing",
      "severity": "warning",
      "retryable": true,
      "summary_ko": "과거 가격 데이터가 준비되지 않았다."
    }
  ],
  "factory_next_actions": [
    {
      "action_code": "prepare_history_dataset",
      "summary_ko": "안전한 데이터 수집 또는 ingest-history 실행 경로를 준비한다.",
      "owner": "automation",
      "safe_to_auto_run": true
    }
  ],
  "factory_retryable": true
}
```

## Diagnostic Codes

- `data_history_missing`: historical dataset or price bars missing.
- `command_contract_error`: command requires arguments or sidecar directory not supplied by package template.
- `insufficient_pass_evidence`: command ran but did not emit a known pass/fail verdict.
- `timeout`: command timed out.
- `unsafe_command`: command references live, broker, SSH, sentinel, capital, whitelist, or caps surface.
- `unsupported_package`: package kind is outside the executor allowlist.
- `missing_command`: package has no executable validation command.
- `execution_failed`: command failed for a reason not otherwise classified.
- `missing_input`: executor input sidecar is absent or malformed.

## Safety Contract

- Diagnostics are additive and must not relax pass criteria.
- Diagnostics must not run new commands.
- Diagnostics must not call broker APIs, place orders, edit live config, edit whitelist/caps, change capital, or write sentinels.
- Diagnostic details must be masked and bounded.
