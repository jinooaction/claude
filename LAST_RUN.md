# 실행 품질 패키지 (as of 2026-09-05T07:28:43Z)

읽기 전용 보고입니다. 이미 발행된 sidecar만 읽어 실행 품질 증거를 묶습니다.
주문, 자본, whitelist, caps, live 전략은 변경하지 않았습니다.

## 종합 판정

| 항목 | 값 |
|------|-----|
| overall_status | OBSERVE |
| monitor_verdict | INSUFFICIENT_DATA |
| latest_signal | INTENT_LOSS |
| cumulative_pnl_usd | -1.14 |
| next_action_ko | 최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다. |

## 브로커 거부 관측

| 항목 | 값 |
|------|-----|
| rejected_orders | 2 |
| parsed_broker_errors | 0 |
| unparsed_reasons | 2 |
| broker_error_observation_rate | 0.0000 |
| kis_msg_codes | {} |

## KIS smoke

| 항목 | 값 |
|------|-----|
| present | True |
| smoke_state | failure |
| smoke_exit | 1 |
| tests_total | 6 |
| tests_failed | 1 |
| smoke_error_rate | 0.1667 |

## 입력 증거

| 증거 | 존재 | 파싱 | 요약 |
|------|:----:|------|------|
| opportunity-monitor | yes | ok | verdict=INSUFFICIENT_DATA, signal=INTENT_LOSS |
| opportunity-history | yes | ok | records=1, rejected_rows=2 |
| rebalance-micro-gtaa | yes | ok | reason=latest_intent_loss |
| kis-smoke | yes | ok | state=failure, exit=1 |

## 안전 경계

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no secret read/write
- no external paid service
- execution-quality evidence package only

## 결정 JSON

```json
{
  "broker_rejections": {
    "broker_error_observation_rate": "0.0000",
    "exception_types": {},
    "http_statuses": {},
    "kis_msg_codes": {},
    "parsed_broker_errors": 0,
    "rejected_orders": 2,
    "unparsed_reasons": 2
  },
  "broker_smoke": {
    "key_valid": true,
    "present": true,
    "smoke_error_rate": "0.1667",
    "smoke_exit": 1,
    "smoke_state": "failure",
    "tests_failed": 1,
    "tests_total": 6,
    "timestamp_utc": "2026-09-05T07:28:24Z"
  },
  "commit": "4a5f43add677155382487f23a8a47debd2daa378",
  "evidence_surfaces": [
    {
      "key": "opportunity-monitor",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/rebalance-micro-gtaa-last-run:opportunity_monitor.json",
      "summary_ko": "verdict=INSUFFICIENT_DATA, signal=INTENT_LOSS"
    },
    {
      "key": "opportunity-history",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/rebalance-micro-gtaa-last-run:opportunity_history.json",
      "summary_ko": "records=1, rejected_rows=2"
    },
    {
      "key": "rebalance-micro-gtaa",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
      "summary_ko": "reason=latest_intent_loss"
    },
    {
      "key": "kis-smoke",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/kis-smoke-last-run:LAST_RUN.md",
      "summary_ko": "state=failure, exit=1"
    }
  ],
  "live_gate": {
    "cumulative_pnl_usd": "-1.14",
    "latest_signal": "INTENT_LOSS",
    "ok": false,
    "present": true,
    "reason": "latest_intent_loss",
    "verdict": "INSUFFICIENT_DATA"
  },
  "opportunity_monitor": {
    "cumulative_pnl_usd": "-1.14",
    "latest_run_id": "[REDACTED_ACCOUNT]",
    "latest_signal": "INTENT_LOSS",
    "next_action_ko": "최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 전략 검토 후 재무장 여부를 판단합니다.",
    "rejected_orders": 2,
    "valued_orders": 2,
    "valued_records": 1,
    "verdict": "INSUFFICIENT_DATA"
  },
  "overall_status": "OBSERVE",
  "run_id": "[REDACTED_ACCOUNT]",
  "safety_invariants": [
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "execution-quality evidence package only"
  ],
  "schema_version": "1.0",
  "timestamp_utc": "2026-09-05T07:28:43Z"
}
```

## workflow metadata

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 4a5f43add677155382487f23a8a47debd2daa378 |
| trigger | workflow_run |
| timestamp_utc | 2026-09-05T07:28:43Z |
| safety | no orders, no capital change, no whitelist/caps change, no live strategy change |
