# 파이프라인 생존 감시 (as of 2026-08-22T16:06:27Z) — 읽기 전용, 돈 0 이동

종합 판정: 🟢 **OK**

| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |
|----------|:----:|:----:|--------:|--------:|-------------|
| rebalance-paper-forward | ✔ | 🟢 OK | 17.2 | 80 | 2026-08-21T22:54:45Z |
| edge-autoarm | ✔ | 🟢 OK | 4.5 | 80 | 2026-08-22T11:33:45Z |
| kis-smoke | ✔ | 🟢 OK | 4.4 | 30 | 2026-08-22T11:43:39Z |
| rebalance-live-canary | ✔ | 🟢 OK | 4.6 | 80 | 2026-08-22T11:31:35Z |
| collect-public-data |  | 🟢 OK | 13.6 | 80 | 2026-08-22T02:32:50Z |
| regime-stratify |  | 🟢 OK | 9.6 | 80 | 2026-08-22T06:28:28Z |
| promote-readiness |  | 🟢 OK | 17.3 | 30 | 2026-08-21T22:47:27Z |
| money-path |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:06Z |
| capital-path-readiness |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:06Z |
| autonomous-work-execution |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:03Z |
| released-work |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:01.976364Z |
| operator-status |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:05.609781Z |
| money-gate-alignment |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:06Z |
| execution-quality |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:06Z |
| profit-evidence-engine |  | 🟢 OK | 4.8 | 30 | 2026-08-22T11:19:28Z |
| autonomous-strategy-factory |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:11Z |
| autonomous-evolution |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:03Z |
| autonomous-promotion |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:05Z |
| candidate-implementation-factory |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:05Z |
| candidate-result-executor |  | 🟢 OK | 4.6 | 30 | 2026-08-22T11:27:53Z |
| autonomous-promotion-actions |  | 🟢 OK | 0.0 | 30 | 2026-08-22T16:06:03Z |
| promotion-forward |  | 🟢 OK | 17.1 | 80 | 2026-08-21T22:59:33Z |
| promotion-canary |  | 🟢 OK | 14.0 | 80 | 2026-08-22T02:04:09Z |
| reassign |  | 🟢 OK | 14.2 | 80 | 2026-08-22T01:53:17Z |


🟢 모든 핵심 사이드카 신선 — 자율 파이프라인 정상 가동.

⚠ 이건 감시 보고다(읽기 전용). 거래·자본 변경 없음 — 라이브는 운영자 게이트(헌법 X.4).

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | f91cc8c94b1f67877bb10fa8011ec58023189983 |
| trigger | workflow_run |
| timestamp_utc | 2026-08-22T16:06:27Z |

## 결정 JSON

```json
{"schema_version": "1.0", "as_of_utc": "2026-08-22T16:06:27Z", "overall": "OK", "checks": [{"key": "rebalance-paper-forward", "status": "OK", "critical": true, "age_hours": 17.2, "max_age_hours": 80.0, "timestamp_utc": "2026-08-21T22:54:45Z", "detail": "전진 페이퍼 A/B 토너먼트(전진 엣지 관측 생산) — 신선(17.2h)."}, {"key": "edge-autoarm", "status": "OK", "critical": true, "age_hours": 4.55, "max_age_hours": 80.0, "timestamp_utc": "2026-08-22T11:33:45Z", "detail": "자본 사다리 게이트(단 승격/강등 결정) — 신선(4.5h)."}, {"key": "kis-smoke", "status": "OK", "critical": true, "age_hours": 4.38, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T11:43:39Z", "detail": "KIS 브로커 연결 생존(매일) — 신선(4.4h)."}, {"key": "rebalance-live-canary", "status": "OK", "critical": true, "age_hours": 4.58, "max_age_hours": 80.0, "timestamp_utc": "2026-08-22T11:31:35Z", "detail": "라이브 캐너리 + 라이브 NAV 스냅샷 — 신선(4.6h)."}, {"key": "collect-public-data", "status": "OK", "critical": false, "age_hours": 13.56, "max_age_hours": 80.0, "timestamp_utc": "2026-08-22T02:32:50Z", "detail": "공개 데이터 수집·교차검증(연구 전용) — 신선(13.6h)."}, {"key": "regime-stratify", "status": "OK", "critical": false, "age_hours": 9.63, "max_age_hours": 80.0, "timestamp_utc": "2026-08-22T06:28:28Z", "detail": "레짐 층화(연구 전용) — 신선(9.6h)."}, {"key": "promote-readiness", "status": "OK", "critical": false, "age_hours": 17.32, "max_age_hours": 30.0, "timestamp_utc": "2026-08-21T22:47:27Z", "detail": "풀라이브 승격 준비 평가(보고 전용) — 신선(17.3h)."}, {"key": "money-path", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:06Z", "detail": "첫-자본까지의 길 종합·ETA(스펙 052, 보고 전용) — 신선(0.0h)."}, {"key": "capital-path-readiness", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:06Z", "detail": "자본 경로 준비도 루프(스펙 076, 보고 전용) — 신선(0.0h)."}, {"key": "autonomous-work-execution", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:03Z", "detail": "자율 작업 실행 루프(스펙 077, 다음 작업 패킷 보고 전용) — 신선(0.0h)."}, {"key": "released-work", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:01.976364Z", "detail": "완료 후보 소비 장부(스펙 079, 보고 전용) — 신선(0.0h)."}, {"key": "operator-status", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:05.609781Z", "detail": "운영자 상태 보고와 모바일 알림 루프(스펙 080, 보고 전용) — 신선(0.0h)."}, {"key": "money-gate-alignment", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:06Z", "detail": "돈 경로 게이트 정렬 루프(스펙 078, 보고 전용) — 신선(0.0h)."}, {"key": "execution-quality", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:06Z", "detail": "주문 거부·체결 품질 패키지(스펙 083, 보고 전용) — 신선(0.0h)."}, {"key": "profit-evidence-engine", "status": "OK", "critical": false, "age_hours": 4.78, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T11:19:28Z", "detail": "시간 분리·비용 차감 수익 후보 검증(스펙 138, 연구 전용) — 신선(4.8h)."}, {"key": "autonomous-strategy-factory", "status": "OK", "critical": false, "age_hours": 0.0, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:11Z", "detail": "64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 신선(0.0h)."}, {"key": "autonomous-evolution", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:03Z", "detail": "영구 자율 성장 루프(스펙 067, 고레버리지 돌파 후보 보고 전용) — 신선(0.0h)."}, {"key": "autonomous-promotion", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:05Z", "detail": "자율 승격 루프(스펙 068, 후보→검증 단계 분류 보고 전용) — 신선(0.0h)."}, {"key": "candidate-implementation-factory", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:05Z", "detail": "후보 구현 공장(스펙 070, BACKTEST_REQUIRED 후보→검증 패키지) — 신선(0.0h)."}, {"key": "candidate-result-executor", "status": "OK", "critical": false, "age_hours": 4.64, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T11:27:53Z", "detail": "후보 결과 실행기(스펙 071, 검증 패키지→결과 evidence) — 신선(4.6h)."}, {"key": "autonomous-promotion-actions", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-22T16:06:03Z", "detail": "자율 승격 실행 루프(스펙 069, forward/canary 큐 연결) — 신선(0.0h)."}, {"key": "promotion-forward", "status": "OK", "critical": false, "age_hours": 17.12, "max_age_hours": 80.0, "timestamp_utc": "2026-08-21T22:59:33Z", "detail": "promotion 전용 forward paper 검증(스펙 069, paper only) — 신선(17.1h)."}, {"key": "promotion-canary", "status": "OK", "critical": false, "age_hours": 14.04, "max_age_hours": 80.0, "timestamp_utc": "2026-08-22T02:04:09Z", "detail": "promotion 전용 hardened canary 검증(스펙 069, live order 없음) — 신선(14.0h)."}, {"key": "reassign", "status": "OK", "critical": false, "age_hours": 14.22, "max_age_hours": 80.0, "timestamp_utc": "2026-08-22T01:53:17Z", "detail": "자율 전략 재지정 폐회로(스펙 055, 챔피언→라이브 5중 게이트) — 신선(14.2h)."}]}
```
