# Contract: execution-quality sidecar

## Probe manifest

`scripts/execution_quality_probe.py --manifest` must emit:

```text
opportunity-monitor	automation/rebalance-micro-gtaa-last-run	opportunity_monitor.json
opportunity-history	automation/rebalance-micro-gtaa-last-run	opportunity_history.json
rebalance-micro-gtaa	automation/rebalance-micro-gtaa-last-run	LAST_RUN.md
kis-smoke	automation/kis-smoke-last-run	LAST_RUN.md
```

## Output JSON

`execution_quality.json` must contain:

```json
{
  "schema_version": "1.0",
  "overall_status": "OBSERVE",
  "opportunity_monitor": {
    "verdict": "INSUFFICIENT_DATA",
    "latest_signal": "INTENT_LOSS",
    "cumulative_pnl_usd": "-1.14",
    "valued_records": 1,
    "rejected_orders": 2,
    "valued_orders": 2,
    "latest_run_id": "28253047287"
  },
  "broker_rejections": {
    "rejected_orders": 2,
    "parsed_broker_errors": 2,
    "broker_error_observation_rate": "1.0000",
    "kis_msg_codes": {
      "APBK1672": 2
    }
  },
  "broker_smoke": {
    "smoke_state": "success",
    "tests_total": 4,
    "tests_failed": 0,
    "smoke_error_rate": "0.0000"
  }
}
```

## Workflow publication

`.github/workflows/execution-quality.yml` publishes:

- `LAST_RUN.md`
- `execution_quality.json`

to `automation/execution-quality-last-run`.

## Evolution evidence contract

`scripts/evolution_loop_probe.py --manifest` must include:

```text
execution-quality	automation/execution-quality-last-run	execution_quality.json
```

The execution-quality candidate must keep the completed candidate id stable:

```json
{
  "candidate_id": "candidate-dff4f9344b02",
  "domain_key": "execution_quality",
  "title_ko": "주문 거부·체결 품질 손익 관측",
  "evidence_refs": [
    "execution-quality",
    "rebalance-micro-gtaa",
    "kis-smoke"
  ]
}
```

When `execution-quality` is missing or stale, the candidate must remain visible but evidence-dependent:

```json
{
  "candidate_id": "candidate-dff4f9344b02",
  "evidence_dependency": "sidecar_freshness",
  "status": "evidence_dependent"
}
```

## Released-work marker

`released-work` consumes only explicit completion markers from fully checked Speckit work. When this spec is merged and post-merge handoff is refreshed, the completed candidate is:

```text
completed_candidate_id: candidate-dff4f9344b02
```

## Safety contract

This feature must not add any of the following to the execution-quality workflow:

- broker API calls
- KIS secrets
- SSH commands
- order submission
- capital allocation
- live strategy change
- whitelist/caps change
- PR creation or merge
