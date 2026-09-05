# 운영자 상태 보고 (as of 2026-09-05T12:47:28.422129Z)

읽기 전용 보고입니다. 자율 루프 진행 상황과 개입 필요 이벤트만 요약합니다.
주문, 자본 배분, live 설정, 서버 SSH, broker 호출은 수행하지 않습니다.

## 종합 판정

| 항목 | 값 |
|------|-----|
| overall_status | ATTENTION |
| headline_ko | 핵심 돈 경로는 막히지 않았지만 일부 보고 sidecar가 늦었습니다. |
| next_action_ko | 지연된 비핵심 sidecar를 상태판에서 확인한다. |
| dashboard_url | https://jinooaction.github.io/claude/status.html |

## 모바일 알림 판정

| 항목 | 값 |
|------|-----|
| alert_level | ATTENTION_ONLY |
| should_send | false |
| send_status | NOT_ATTEMPTED |
| reason_ko | 보조 확인 항목만 있어 모바일 알림은 보내지 않습니다. |

## 입력 표면

| 표면 | 존재 | 파싱 | 상태 | 심각도 | 요약 | 다음 행동 |
|------|:----:|------|------|--------|------|-----------|
| pipeline-liveness | yes | ok | DEGRADED | attention | 핵심 돈 경로는 막히지 않았지만 일부 보고 sidecar가 늦었습니다. | 지연된 비핵심 sidecar를 상태판에서 확인한다. |
| money-path | yes | ok | REAL_ORDER_PATH_ARMED | attention | 실제 주문 경로가 무장 상태입니다. 최신 주문 sidecar와 감사 로그를 함께 봐야 합니다. | micro GTAA와 live canary 최신 sidecar를 확인한다. |
| capital-path-readiness | yes | ok | CAPITAL_ARMABLE | info | 자본 준비도는 CAPITAL_ARMABLE, 실제 돈 상태는 REAL_ORDER_PATH_ARMED입니다. |  |
| money-gate-alignment | yes | ok | ALIGNED_WAITING | info | 돈 경로 정렬 상태는 ALIGNED_WAITING입니다. | 전진 관측을 계속 누적하고, 최소 관측 이후 기존 자본 사다리로만 승격한다. |
| autonomous-work-execution | yes | ok | EXECUTION_READY | info | 다음 자율 작업은 실거래 관찰과 병렬인 신규 엣지 challenger입니다. | 공개 데이터·레짐·비용·paper forward를 사용해 기존 후보와 다른 신호군을 시간 분리 walk-forward로 검증하고, 통과하지 못하면 live 승격 없이 기각한다. |
| released-work | yes | ok | OK | info | 완료 후보 장부 상태는 OK, 완료 후보 61개입니다. |  |

## 안전 경계

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no server SSH
- no secret persistence
- operator visibility only

## 결정 JSON

```json
{
  "alert_decision": {
    "alert_level": "ATTENTION_ONLY",
    "message_ko": "auto-invest 운영자 알림: ATTENTION\n핵심 돈 경로는 막히지 않았지만 일부 보고 sidecar가 늦었습니다.\n\n다음 행동: 지연된 비핵심 sidecar를 상태판에서 확인한다.\n\n상태판: https://jinooaction.github.io/claude/status.html\n\n읽기 전용 알림입니다. 주문, 자본, live 설정은 변경하지 않았습니다.",
    "reason_ko": "보조 확인 항목만 있어 모바일 알림은 보내지 않습니다.",
    "send_status": "NOT_ATTEMPTED",
    "should_send": false
  },
  "commit": "4a5f43add677155382487f23a8a47debd2daa378",
  "dashboard_sections": [
    {
      "body_ko": "실제 주문 경로가 무장 상태입니다. 최신 주문 sidecar와 감사 로그를 함께 봐야 합니다.",
      "key": "money",
      "status": "REAL_ORDER_PATH_ARMED",
      "title_ko": "실제 돈 경로"
    },
    {
      "body_ko": "다음 자율 작업은 실거래 관찰과 병렬인 신규 엣지 challenger입니다.",
      "key": "autonomous-work",
      "status": "EXECUTION_READY",
      "title_ko": "다음 자율 작업"
    },
    {
      "body_ko": "돈 경로 정렬 상태는 ALIGNED_WAITING입니다.",
      "key": "alignment",
      "status": "ALIGNED_WAITING",
      "title_ko": "돈 경로 정렬"
    },
    {
      "body_ko": "개입 필요 항목이 없습니다.",
      "key": "action-needed",
      "status": "OK",
      "title_ko": "개입 필요"
    }
  ],
  "dashboard_url": "https://jinooaction.github.io/claude/status.html",
  "headline_ko": "핵심 돈 경로는 막히지 않았지만 일부 보고 sidecar가 늦었습니다.",
  "next_action_ko": "지연된 비핵심 sidecar를 상태판에서 확인한다.",
  "overall_status": "ATTENTION",
  "run_id": "[REDACTED_ACCOUNT]",
  "safety_invariants": [
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no server SSH",
    "no secret persistence",
    "operator visibility only"
  ],
  "schema_version": "1.0",
  "surfaces": [
    {
      "key": "pipeline-liveness",
      "next_action_ko": "지연된 비핵심 sidecar를 상태판에서 확인한다.",
      "parse_status": "ok",
      "present": true,
      "severity": "attention",
      "source_ref": "automation/pipeline-liveness-last-run:LAST_RUN.md",
      "status": "DEGRADED",
      "summary_ko": "핵심 돈 경로는 막히지 않았지만 일부 보고 sidecar가 늦었습니다."
    },
    {
      "key": "money-path",
      "next_action_ko": "micro GTAA와 live canary 최신 sidecar를 확인한다.",
      "parse_status": "ok",
      "present": true,
      "severity": "attention",
      "source_ref": "automation/money-path-last-run:LAST_RUN.md",
      "status": "REAL_ORDER_PATH_ARMED",
      "summary_ko": "실제 주문 경로가 무장 상태입니다. 최신 주문 sidecar와 감사 로그를 함께 봐야 합니다."
    },
    {
      "key": "capital-path-readiness",
      "next_action_ko": "",
      "parse_status": "ok",
      "present": true,
      "severity": "info",
      "source_ref": "automation/capital-path-readiness-last-run:capital_path_readiness.json",
      "status": "CAPITAL_ARMABLE",
      "summary_ko": "자본 준비도는 CAPITAL_ARMABLE, 실제 돈 상태는 REAL_ORDER_PATH_ARMED입니다."
    },
    {
      "key": "money-gate-alignment",
      "next_action_ko": "전진 관측을 계속 누적하고, 최소 관측 이후 기존 자본 사다리로만 승격한다.",
      "parse_status": "ok",
      "present": true,
      "severity": "info",
      "source_ref": "automation/money-gate-alignment-last-run:money_gate_alignment.json",
      "status": "ALIGNED_WAITING",
      "summary_ko": "돈 경로 정렬 상태는 ALIGNED_WAITING입니다."
    },
    {
      "key": "autonomous-work-execution",
      "next_action_ko": "공개 데이터·레짐·비용·paper forward를 사용해 기존 후보와 다른 신호군을 시간 분리 walk-forward로 검증하고, 통과하지 못하면 live 승격 없이 기각한다.",
      "parse_status": "ok",
      "present": true,
      "severity": "info",
      "source_ref": "automation/autonomous-work-execution-last-run:autonomous_work_execution.json",
      "status": "EXECUTION_READY",
      "summary_ko": "다음 자율 작업은 실거래 관찰과 병렬인 신규 엣지 challenger입니다."
    },
    {
      "key": "released-work",
      "next_action_ko": "",
      "parse_status": "ok",
      "present": true,
      "severity": "info",
      "source_ref": "automation/released-work-last-run:released_work.json",
      "status": "OK",
      "summary_ko": "완료 후보 장부 상태는 OK, 완료 후보 61개입니다."
    }
  ],
  "timestamp_utc": "2026-09-05T12:47:28.422129Z"
}
```
