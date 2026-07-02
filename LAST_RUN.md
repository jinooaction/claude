# 완료 후보 소비 장부 (as of 2026-07-02T04:11:47.803767Z)

읽기 전용 보고입니다. 완료된 작업 후보를 다음 자율 작업 선택에서 제외하기 위한 장부입니다.
주문, 자본 배분, live 설정 변경, 코드 자동 수정, PR 자동 생성은 하지 않습니다.

## 종합 판정

| 항목 | 값 |
|------|-----|
| overall_status | OK |
| released_count | 2 |
| scanned_specs | 32 |

## 완료 후보

| 후보 | 상태 | 스펙 | 근거 파일 | 근거 필드 |
|------|------|------|-----------|-----------|
| candidate-fd04772a23c5 | released | 078-money-gate-alignment-loop | specs/078-money-gate-alignment-loop/contracts/money-gate-alignment.md | selected_work_candidate |
| candidate-fd04772a23c5 | released | 079-completed-candidate-consumption | specs/079-completed-candidate-consumption/spec.md | selected_work_candidate |

## 제외한 스펙

| 스펙 | 이유 |
|------|------|
| 001-automated-trading-mvp | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 003-session-cache | tasks.md를 읽을 수 없습니다. |
| 009-paper-trading-daemon | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 013-operational-health | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 015-live-fill-ingestion | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 016-backtest-cost-model | tasks.md를 읽을 수 없습니다. |
| 017-volatility-position-sizing | tasks.md를 읽을 수 없습니다. |
| 018-multifactor-signals | tasks.md를 읽을 수 없습니다. |
| 019-regime-erc-sizing | tasks.md를 읽을 수 없습니다. |
| 020-regime-erc-wiring | tasks.md를 읽을 수 없습니다. |
| 021-cross-sectional-ranking | tasks.md를 읽을 수 없습니다. |
| 025-composite-factor-alpha | tasks.md를 읽을 수 없습니다. |
| 026-canary-fulllive-promotion | tasks.md를 읽을 수 없습니다. |
| 027-deflated-sharpe-significance | tasks.md를 읽을 수 없습니다. |
| 028-execution-quality-precision | tasks.md를 읽을 수 없습니다. |
| 029-portfolio-nav-tracking | tasks.md를 읽을 수 없습니다. |
| 030-order-lifecycle | tasks.md를 읽을 수 없습니다. |
| 031-realtime-websocket | tasks.md를 읽을 수 없습니다. |
| 032-portfolio-rebalancing | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 033-kis-daily-bar-backfill | tasks.md를 읽을 수 없습니다. |
| 038-calmar-capital-defense | tasks.md를 읽을 수 없습니다. |
| 039-live-canary-portfolio | tasks.md를 읽을 수 없습니다. |
| 040-live-canary-arming | tasks.md를 읽을 수 없습니다. |
| 041-absolute-return-gate | tasks.md를 읽을 수 없습니다. |
| 042-risk-managed-beta | tasks.md를 읽을 수 없습니다. |
| 043-multi-asset-trend | tasks.md를 읽을 수 없습니다. |
| 044-growth-optimal-leverage | tasks.md를 읽을 수 없습니다. |
| 045-regime-recency-audit | tasks.md를 읽을 수 없습니다. |
| 046-strategy-monitor | tasks.md를 읽을 수 없습니다. |
| 047-global-trend | tasks.md를 읽을 수 없습니다. |
| 048-trend-ensemble | tasks.md를 읽을 수 없습니다. |
| 050-capital-ladder | tasks.md를 읽을 수 없습니다. |
| 051-pipeline-liveness | tasks.md를 읽을 수 없습니다. |
| 052-money-path-readiness | tasks.md를 읽을 수 없습니다. |
| 054-uncorrelated-alpha | tasks.md를 읽을 수 없습니다. |
| 055-autonomous-reassignment | tasks.md를 읽을 수 없습니다. |
| 056-agent-harness-eval | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 059-kis-order-diagnostics | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 063-account-wide-micro-gtaa | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 066-strategy-review-observation-health | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 068-autonomous-promotion-loop | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 070-candidate-implementation-factory | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 071-candidate-result-executor | 체크박스 작업이 없거나 완료되지 않았습니다. |
| 072-candidate-evidence-diagnostics | 체크박스 작업이 없거나 완료되지 않았습니다. |

## 안전 경계

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no secret read/write
- no external paid service
- released-work ledger only

## 결정 JSON

```json
{
  "commit": "a98db6edae2834643d941dc1a14230d6818aa9dd",
  "overall_status": "OK",
  "released_work": [
    {
      "candidate_id": "candidate-fd04772a23c5",
      "entry_id": "released-c16b3365c562",
      "reason_ko": "완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "source_field": "selected_work_candidate",
      "source_file": "specs/078-money-gate-alignment-loop/contracts/money-gate-alignment.md",
      "spec_id": "078-money-gate-alignment-loop",
      "status": "released"
    },
    {
      "candidate_id": "candidate-fd04772a23c5",
      "entry_id": "released-552c7027b931",
      "reason_ko": "완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "source_field": "selected_work_candidate",
      "source_file": "specs/079-completed-candidate-consumption/spec.md",
      "spec_id": "079-completed-candidate-consumption",
      "status": "released"
    }
  ],
  "run_id": "28564808405",
  "safety_invariants": [
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "released-work ledger only"
  ],
  "scanned_specs": [
    "002-token-telemetry",
    "004-llm-judgment-points",
    "005-autonomous-tuner",
    "006-deploy-automation",
    "007-canary-hardening",
    "008-backtest-engine",
    "010-auto-rule-designer",
    "011-live-performance-eval",
    "012-tuner-canary-queue",
    "014-loss-circuit-breaker",
    "034-universe-construction",
    "035-forward-edge-verdict",
    "036-trend-filter",
    "037-forward-ab-tournament",
    "057-agent-quality-redteam",
    "058-micro-gtaa-canary",
    "060-telegram-order-alerts",
    "061-telegram-server-connect",
    "062-money-path-state",
    "064-rejected-opportunity-feedback",
    "065-micro-gtaa-intent-loss-gate",
    "067-autonomous-evolution-loop",
    "069-autonomous-promotion-actions",
    "073-candidate-pending-next-actions",
    "074-candidate-history-support",
    "075-strategy-failure-learning",
    "076-capital-path-readiness-loop",
    "077-autonomous-work-execution-loop",
    "078-money-gate-alignment-loop",
    "079-completed-candidate-consumption",
    "080-operator-dashboard-alert-loop",
    "081-autonomous-loop-quality-closure"
  ],
  "schema_version": "1.0",
  "skipped_specs": [
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "001-automated-trading-mvp"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "003-session-cache"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "009-paper-trading-daemon"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "013-operational-health"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "015-live-fill-ingestion"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "016-backtest-cost-model"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "017-volatility-position-sizing"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "018-multifactor-signals"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "019-regime-erc-sizing"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "020-regime-erc-wiring"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "021-cross-sectional-ranking"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "025-composite-factor-alpha"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "026-canary-fulllive-promotion"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "027-deflated-sharpe-significance"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "028-execution-quality-precision"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "029-portfolio-nav-tracking"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "030-order-lifecycle"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "031-realtime-websocket"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "032-portfolio-rebalancing"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "033-kis-daily-bar-backfill"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "038-calmar-capital-defense"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "039-live-canary-portfolio"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "040-live-canary-arming"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "041-absolute-return-gate"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "042-risk-managed-beta"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "043-multi-asset-trend"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "044-growth-optimal-leverage"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "045-regime-recency-audit"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "046-strategy-monitor"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "047-global-trend"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "048-trend-ensemble"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "050-capital-ladder"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "051-pipeline-liveness"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "052-money-path-readiness"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "054-uncorrelated-alpha"
    },
    {
      "reason_ko": "tasks.md를 읽을 수 없습니다.",
      "spec_id": "055-autonomous-reassignment"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "056-agent-harness-eval"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "059-kis-order-diagnostics"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "063-account-wide-micro-gtaa"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "066-strategy-review-observation-health"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "068-autonomous-promotion-loop"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "070-candidate-implementation-factory"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "071-candidate-result-executor"
    },
    {
      "reason_ko": "체크박스 작업이 없거나 완료되지 않았습니다.",
      "spec_id": "072-candidate-evidence-diagnostics"
    }
  ],
  "timestamp_utc": "2026-07-02T04:11:47.803767Z"
}
```
