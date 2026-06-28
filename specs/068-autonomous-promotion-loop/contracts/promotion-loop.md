# Contract: Autonomous Promotion Loop Artifacts

## Inputs

The probe reads a directory of collected evidence files:

- `candidate_backlog.json`: autonomous evolution candidate backlog.
- `evolution_summary.json`: autonomous evolution latest summary.
- `money-path.md`: latest money-path sidecar.
- `rebalance-paper-forward.md`: latest forward paper sidecar.
- `reassign.md`: latest reassignment sidecar.
- Optional additional `*.md` or `*.json` notes.

## Outputs

### `promotion_summary.json`

```json
{
  "schema_version": "1.0",
  "run_id": "github-run-id",
  "commit": "sha",
  "timestamp_utc": "2026-06-29T08:45:00Z",
  "overall_status": "ok",
  "assessments": [
    {
      "candidate_id": "candidate-abc",
      "stage": "BACKTEST_REQUIRED",
      "allowed_next_action": "과거+표본외+walk-forward 백테스트 패키지를 먼저 만든다.",
      "strategy_validation_complete": false,
      "execution_validation_complete": false,
      "next_gate": null
    }
  ]
}
```

### `promotion_queue.json`

```json
{
  "schema_version": "1.0",
  "queue": [
    {
      "candidate_id": "candidate-abc",
      "stage": "BACKTEST_REQUIRED",
      "priority_score": 618
    }
  ]
}
```

### `LAST_RUN.md`

Korean operator report with:

- one-line status
- top promotion queue
- backtest vs small-live distinction
- existing gate routing
- missing evidence
- safety statement
