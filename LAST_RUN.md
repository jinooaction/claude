# 자본 경로 준비도 루프 (as of 2026-09-05T11:49:03Z)

읽기 전용 보고입니다. 주문, 자본 배분, 라이브 설정 변경은 하지 않습니다.

## 종합 판정

| 항목 | 값 |
|------|-----|
| readiness_state | CAPITAL_ARMABLE |
| live_money_status | REAL_ORDER_PATH_ARMED |
| capital_ladder_stage | DEPLOYED |
| blocking_gate | 20% 승격은 별도 깨끗한 전진 40관측·PSR 0.80·칼마 우위·전체 경로 교정 필요. |
| next_action_ko | 예약 라이브 실행으로 실제 주문·체결·정합·감사를 확인하되 단1을 유지한다. 20%는 깨끗한 전진 알파 계약을 따로 벌어야 한다. |
| required_existing_gates | money-path, edge-autoarm, reassign, production environment machine authorization, non-push workflow event, US regular session, KIS purchasable cash >= planned buys + 1% buffer, portfolio circuit breaker clear, K1 caps and K2 whitelist |

## 우선 후보

- 현재 자본 경로 준비도를 높이는 우선 후보 없음.

## 억제 후보

| 후보 | 영역 | 상태 | 출처 | 이유 |
|------|------|------|------|------|
| candidate-1ed634d8bf6d |  | rejected | evolution-ledger | 기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다. |
| candidate-cc96b35062da |  | rejected | evolution-ledger | 기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다. |
| candidate-fd04772a23c5 | live_readiness | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |
| candidate-source-diversification-sidecar-bottleneck | agent_ops | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |
| candidate-88a7e7f07361 | agent_ops | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |
| candidate-e481b0309206 | analysis | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |
| candidate-fa66202bf496 | review | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |
| candidate-dff4f9344b02 | execution_quality | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |
| candidate-6ee3370e933d | data_quality | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |
| candidate-facf2fa31834 | data_collection | released | evolution-backlog+released-work | released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다. |

## 관측 이슈

| 이슈 | 심각도 | 출처 | 상태 | 요약 | 다음 조치 |
|------|--------|------|------|------|-----------|
| released-candidate-echo:candidate-fd04772a23c5 | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| released-candidate-echo:candidate-source-diversification-sidecar-bottleneck | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| released-candidate-echo:candidate-88a7e7f07361 | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| released-candidate-echo:candidate-e481b0309206 | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| released-candidate-echo:candidate-fa66202bf496 | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| released-candidate-echo:candidate-dff4f9344b02 | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| released-candidate-echo:candidate-6ee3370e933d | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| released-candidate-echo:candidate-facf2fa31834 | info | released-work | RELEASED | 이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다. | released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다. |
| pipeline-liveness:autonomous-strategy-factory | warning | autonomous-strategy-factory | STALE | autonomous-strategy-factory sidecar 상태가 STALE입니다. 64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 70.3h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다. | 해당 sidecar의 마지막 workflow 실행과 발행 시각을 확인합니다. |

## 입력 증거

| 증거 | 존재 | 파싱 | 요약 |
|------|:----:|------|------|
| money-path | yes | ok | stage=DEPLOYED, live=REAL_ORDER_PATH_ARMED |
| edge-autoarm | yes | ok | 자본 사다리 원천 sidecar 존재 |
| reassign | yes | ok | reassign 판정 JSON 확인 |
| rebalance-paper-forward | yes | ok | 전진 페이퍼 관측 sidecar 존재 |
| kis-smoke | yes | present | KIS smoke sidecar 존재 |
| autonomous-promotion | yes | ok | 승격 요약 JSON 확인 |
| evolution-backlog | yes | ok | 후보 10개 확인 |
| evolution-ledger | yes | ok | 억제 후보 2개 확인 |
| released-work | yes | ok | 완료 후보 60개 확인 |
| pipeline-liveness | yes | ok | overall=DEGRADED |

## 안전 경계

- 이 루프는 기존 sidecar를 읽고 자기 sidecar만 발행합니다.
- 실제 주문, 실거래 전환, 자본 배분, whitelist/caps/live 설정 변경을 하지 않습니다.
- 자본 투입 판단은 기존 `money-path`, `edge-autoarm`, `reassign` 게이트를 유지합니다.

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 4a5f43add677155382487f23a8a47debd2daa378 |
| trigger | schedule |
| timestamp_utc | 2026-09-05T11:49:03Z |

## 결정 JSON

```json
{
  "blocking_gate": "20% 승격은 별도 깨끗한 전진 40관측·PSR 0.80·칼마 우위·전체 경로 교정 필요.",
  "capital_ladder_stage": "DEPLOYED",
  "commit": "4a5f43add677155382487f23a8a47debd2daa378",
  "evidence_surfaces": [
    {
      "key": "money-path",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/money-path-last-run:LAST_RUN.md",
      "summary_ko": "stage=DEPLOYED, live=REAL_ORDER_PATH_ARMED"
    },
    {
      "key": "edge-autoarm",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/edge-autoarm-last-run:LAST_RUN.md",
      "summary_ko": "자본 사다리 원천 sidecar 존재"
    },
    {
      "key": "reassign",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/reassign-last-run:LAST_RUN.md",
      "summary_ko": "reassign 판정 JSON 확인"
    },
    {
      "key": "rebalance-paper-forward",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
      "summary_ko": "전진 페이퍼 관측 sidecar 존재"
    },
    {
      "key": "kis-smoke",
      "parse_status": "present",
      "present": true,
      "source_ref": "automation/kis-smoke-last-run:LAST_RUN.md",
      "summary_ko": "KIS smoke sidecar 존재"
    },
    {
      "key": "autonomous-promotion",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/autonomous-promotion-last-run:promotion_summary.json",
      "summary_ko": "승격 요약 JSON 확인"
    },
    {
      "key": "evolution-backlog",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/autonomous-evolution-last-run:candidate_backlog.json",
      "summary_ko": "후보 10개 확인"
    },
    {
      "key": "evolution-ledger",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/autonomous-evolution-last-run:learning_ledger.json",
      "summary_ko": "억제 후보 2개 확인"
    },
    {
      "key": "released-work",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/released-work-last-run:released_work.json",
      "summary_ko": "완료 후보 60개 확인"
    },
    {
      "key": "pipeline-liveness",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/pipeline-liveness-last-run:LAST_RUN.md",
      "summary_ko": "overall=DEGRADED"
    }
  ],
  "live_money_status": "REAL_ORDER_PATH_ARMED",
  "next_action_ko": "예약 라이브 실행으로 실제 주문·체결·정합·감사를 확인하되 단1을 유지한다. 20%는 깨끗한 전진 알파 계약을 따로 벌어야 한다.",
  "observability_issues": [
    {
      "affected_candidate_id": "candidate-fd04772a23c5",
      "issue_id": "released-candidate-echo:candidate-fd04772a23c5",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": "candidate-source-diversification-sidecar-bottleneck",
      "issue_id": "released-candidate-echo:candidate-source-diversification-sidecar-bottleneck",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": "candidate-88a7e7f07361",
      "issue_id": "released-candidate-echo:candidate-88a7e7f07361",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": "candidate-e481b0309206",
      "issue_id": "released-candidate-echo:candidate-e481b0309206",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": "candidate-fa66202bf496",
      "issue_id": "released-candidate-echo:candidate-fa66202bf496",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": "candidate-dff4f9344b02",
      "issue_id": "released-candidate-echo:candidate-dff4f9344b02",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": "candidate-6ee3370e933d",
      "issue_id": "released-candidate-echo:candidate-6ee3370e933d",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": "candidate-facf2fa31834",
      "issue_id": "released-candidate-echo:candidate-facf2fa31834",
      "issue_type": "released_candidate_echo",
      "next_action_ko": "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다.",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 evolution-backlog 후보 목록에 남아 있습니다."
    },
    {
      "affected_candidate_id": null,
      "issue_id": "pipeline-liveness:autonomous-strategy-factory",
      "issue_type": "pipeline_liveness",
      "next_action_ko": "해당 sidecar의 마지막 workflow 실행과 발행 시각을 확인합니다.",
      "severity": "warning",
      "source_key": "autonomous-strategy-factory",
      "status": "STALE",
      "summary_ko": "autonomous-strategy-factory sidecar 상태가 STALE입니다. 64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 70.3h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다."
    }
  ],
  "priority_candidates": [],
  "readiness_state": "CAPITAL_ARMABLE",
  "required_existing_gates": [
    "money-path",
    "edge-autoarm",
    "reassign",
    "production environment machine authorization",
    "non-push workflow event",
    "US regular session",
    "KIS purchasable cash >= planned buys + 1% buffer",
    "portfolio circuit breaker clear",
    "K1 caps and K2 whitelist"
  ],
  "run_id": "[REDACTED_ACCOUNT]",
  "schema_version": "1.0",
  "suppressed_candidates": [
    {
      "candidate_id": "candidate-1ed634d8bf6d",
      "domain_key": "",
      "reason_ko": "기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다.",
      "score": null,
      "source": "evolution-ledger",
      "status": "rejected",
      "title_ko": "제목 없음"
    },
    {
      "candidate_id": "candidate-cc96b35062da",
      "domain_key": "",
      "reason_ko": "기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다.",
      "score": null,
      "source": "evolution-ledger",
      "status": "rejected",
      "title_ko": "제목 없음"
    },
    {
      "candidate_id": "candidate-fd04772a23c5",
      "domain_key": "live_readiness",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 597,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "돈 경로 준비도와 기존 게이트 정렬"
    },
    {
      "candidate_id": "candidate-source-diversification-sidecar-bottleneck",
      "domain_key": "agent_ops",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 594,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "증거 기반 후보 소스 다변화"
    },
    {
      "candidate_id": "candidate-88a7e7f07361",
      "domain_key": "agent_ops",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 568,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "자율 루프 sidecar와 handoff 생존성"
    },
    {
      "candidate_id": "candidate-e481b0309206",
      "domain_key": "analysis",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 560,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "레짐·성과 분석을 후보 점수화 입력으로 승격"
    },
    {
      "candidate_id": "candidate-fa66202bf496",
      "domain_key": "review",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 559,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "학습 장부로 폐기·보류 후보 재발굴 차단"
    },
    {
      "candidate_id": "candidate-dff4f9344b02",
      "domain_key": "execution_quality",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 527,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "주문 거부·체결 품질 손익 관측"
    },
    {
      "candidate_id": "candidate-6ee3370e933d",
      "domain_key": "data_quality",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 524,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "오래된 증거와 성과 실패 분리"
    },
    {
      "candidate_id": "candidate-facf2fa31834",
      "domain_key": "data_collection",
      "reason_ko": "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 작업 후보가 아니라 관측 잔향으로 분리했다.",
      "score": 494,
      "source": "evolution-backlog+released-work",
      "status": "released",
      "title_ko": "공개 데이터 수집·교차 검증 확장"
    }
  ],
  "timestamp_utc": "2026-09-05T11:49:03Z"
}
```
