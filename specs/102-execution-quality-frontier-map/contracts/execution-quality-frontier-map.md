# Contract: Execution Quality Frontier Map

completed_candidate_id: candidate-execution-quality-frontier-map

## Autonomous-work JSON additions

The report includes:

```json
{
  "execution_quality_frontier_map": [
    {
      "frontier_key": "broker_rejection_taxonomy",
      "label_ko": "브로커 거부 분류",
      "coverage_status": "open",
      "priority_score": 2150,
      "recommended_candidate_id": "candidate-broker-rejection-taxonomy-contract",
      "title_ko": "브로커 거부 분류 계약",
      "reason_ko": "execution-quality sidecar는 거부 주문과 KIS 오류 코드를 관측하지만, 거부 원인 분류와 재발 기준은 별도 후보로 닫혀 있지 않다.",
      "next_action_ko": "execution-quality, rebalance-micro-gtaa, kis-smoke 증거를 함께 읽어 브로커 거부 코드·원인·재발 가능성을 분류하는 읽기 전용 계약을 만든다.",
      "required_inputs": [
        "automation/execution-quality-last-run:LAST_RUN.md",
        "automation/kis-smoke-last-run:LAST_RUN.md",
        "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
      ]
    }
  ]
}
```

## Markdown additions

The report includes a section headed:

```text
## 체결 품질 frontier 지도
```

## Selection rule

When `candidate-execution-quality-frontier-map` is not released, it remains the selected macro candidate. When it is released, the selected work packet advances to the highest-priority unreleased entry in `execution_quality_frontier_map`.

## Safety rule

This contract is read-only. It does not call broker APIs, submit orders, allocate capital, change live strategy, widen whitelist/caps, read or write secrets, modify constitution/kernel files, or invoke paid external services.

