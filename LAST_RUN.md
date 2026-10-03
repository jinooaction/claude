# 파이프라인 생존 감시 (as of 2026-10-03T14:20:51Z) — 읽기 전용, 돈 0 이동

종합 판정: 🟡 **DEGRADED**

| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |
|----------|:----:|:----:|--------:|--------:|-------------|
| rebalance-paper-forward | ✔ | 🟢 OK | 13.0 | 80 | 2026-10-03T01:21:38Z |
| edge-autoarm | ✔ | 🟢 OK | 12.0 | 80 | 2026-10-03T02:22:30Z |
| kis-smoke | ✔ | 🟢 OK | 5.4 | 30 | 2026-10-03T08:57:42Z |
| rebalance-live-canary | ✔ | 🟢 OK | 18.4 | 80 | 2026-10-02T19:56:25Z |
| collect-public-data |  | 🟢 OK | 7.6 | 80 | 2026-10-03T06:46:24Z |
| regime-stratify |  | 🟢 OK | 12.1 | 80 | 2026-10-03T02:14:53Z |
| regime-challenger-forward |  | 🟢 OK | 409.7 | 840 | 2026-09-16T12:39:54Z |
| promote-readiness |  | 🟢 OK | 13.1 | 30 | 2026-10-03T01:15:38Z |
| money-path |  | 🟢 OK | 1.3 | 30 | 2026-10-03T13:01:12Z |
| capital-path-readiness |  | 🟢 OK | 1.0 | 30 | 2026-10-03T13:20:27Z |
| autonomous-work-execution |  | 🟢 OK | 0.0 | 30 | 2026-10-03T14:17:59Z |
| released-work |  | 🟢 OK | 0.2 | 30 | 2026-10-03T14:10:49.464621Z |
| operator-status |  | 🟢 OK | 0.0 | 30 | 2026-10-03T14:20:28.155750Z |
| money-gate-alignment |  | 🟢 OK | 0.0 | 30 | 2026-10-03T14:20:14Z |
| execution-quality |  | 🟢 OK | 5.4 | 30 | 2026-10-03T08:57:58Z |
| profit-evidence-engine |  | 🟢 OK | 0.1 | 30 | 2026-10-03T14:17:28Z |
| autonomous-strategy-factory |  | 🔴 STALE | 745.2 | 30 | 2026-09-02T13:06:16Z |
| autonomous-evolution |  | 🟢 OK | 0.8 | 30 | 2026-10-03T13:32:59Z |
| autonomous-promotion |  | 🟢 OK | 0.4 | 30 | 2026-10-03T13:56:29Z |
| candidate-implementation-factory |  | 🟢 OK | 0.4 | 30 | 2026-10-03T13:55:49Z |
| candidate-result-executor |  | 🟢 OK | 0.4 | 30 | 2026-10-03T13:56:39Z |
| autonomous-promotion-actions |  | 🟢 OK | 0.2 | 30 | 2026-10-03T14:06:45Z |
| promotion-forward |  | 🟢 OK | 12.9 | 80 | 2026-10-03T01:27:05Z |
| promotion-canary |  | 🟢 OK | 8.6 | 80 | 2026-10-03T05:44:00Z |
| reassign |  | 🟢 OK | 8.9 | 80 | 2026-10-03T05:26:11Z |

- **autonomous-strategy-factory** (STALE): 64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 745.2h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다.

⚠ 이건 감시 보고다(읽기 전용). 거래·자본 변경 없음 — 라이브는 운영자 게이트(헌법 X.4).

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 9d70758cd505844dc673291ba98651131be670b7 |
| trigger | workflow_run |
| timestamp_utc | 2026-10-03T14:20:51Z |

## 결정 JSON

```json
{"schema_version": "1.0", "as_of_utc": "2026-10-03T14:20:51Z", "overall": "DEGRADED", "checks": [{"key": "rebalance-paper-forward", "status": "OK", "critical": true, "age_hours": 12.99, "max_age_hours": 80.0, "timestamp_utc": "2026-10-03T01:21:38Z", "detail": "전진 페이퍼 A/B 토너먼트(전진 엣지 관측 생산) — 신선(13.0h)."}, {"key": "edge-autoarm", "status": "OK", "critical": true, "age_hours": 11.97, "max_age_hours": 80.0, "timestamp_utc": "2026-10-03T02:22:30Z", "detail": "자본 사다리 게이트(단 승격/강등 결정) — 신선(12.0h)."}, {"key": "kis-smoke", "status": "OK", "critical": true, "age_hours": 5.39, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T08:57:42Z", "detail": "KIS 브로커 연결 생존(매일) — 신선(5.4h)."}, {"key": "rebalance-live-canary", "status": "OK", "critical": true, "age_hours": 18.41, "max_age_hours": 80.0, "timestamp_utc": "2026-10-02T19:56:25Z", "detail": "라이브 캐너리 + 라이브 NAV 스냅샷 — 신선(18.4h)."}, {"key": "collect-public-data", "status": "OK", "critical": false, "age_hours": 7.57, "max_age_hours": 80.0, "timestamp_utc": "2026-10-03T06:46:24Z", "detail": "공개 데이터 수집·교차검증(연구 전용) — 신선(7.6h)."}, {"key": "regime-stratify", "status": "OK", "critical": false, "age_hours": 12.1, "max_age_hours": 80.0, "timestamp_utc": "2026-10-03T02:14:53Z", "detail": "레짐 층화(연구 전용) — 신선(12.1h)."}, {"key": "regime-challenger-forward", "status": "OK", "critical": false, "age_hours": 409.68, "max_age_hours": 840.0, "timestamp_utc": "2026-09-16T12:39:54Z", "detail": "7/8 레짐 후보 동결 후 월별 관찰(주문 없는 연구 전용) — 신선(409.7h)."}, {"key": "promote-readiness", "status": "OK", "critical": false, "age_hours": 13.09, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T01:15:38Z", "detail": "풀라이브 승격 준비 평가(보고 전용) — 신선(13.1h)."}, {"key": "money-path", "status": "OK", "critical": false, "age_hours": 1.33, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T13:01:12Z", "detail": "첫-자본까지의 길 종합·ETA(스펙 052, 보고 전용) — 신선(1.3h)."}, {"key": "capital-path-readiness", "status": "OK", "critical": false, "age_hours": 1.01, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T13:20:27Z", "detail": "자본 경로 준비도 루프(스펙 076, 보고 전용) — 신선(1.0h)."}, {"key": "autonomous-work-execution", "status": "OK", "critical": false, "age_hours": 0.05, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T14:17:59Z", "detail": "자율 작업 실행 루프(스펙 077, 다음 작업 패킷 보고 전용) — 신선(0.0h)."}, {"key": "released-work", "status": "OK", "critical": false, "age_hours": 0.17, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T14:10:49.464621Z", "detail": "완료 후보 소비 장부(스펙 079, 보고 전용) — 신선(0.2h)."}, {"key": "operator-status", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T14:20:28.155750Z", "detail": "운영자 상태 보고와 모바일 알림 루프(스펙 080, 보고 전용) — 신선(0.0h)."}, {"key": "money-gate-alignment", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T14:20:14Z", "detail": "돈 경로 게이트 정렬 루프(스펙 078, 보고 전용) — 신선(0.0h)."}, {"key": "execution-quality", "status": "OK", "critical": false, "age_hours": 5.38, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T08:57:58Z", "detail": "주문 거부·체결 품질 패키지(스펙 083, 보고 전용) — 신선(5.4h)."}, {"key": "profit-evidence-engine", "status": "OK", "critical": false, "age_hours": 0.06, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T14:17:28Z", "detail": "시간 분리·비용 차감 수익 후보 검증(스펙 138, 연구 전용) — 신선(0.1h)."}, {"key": "autonomous-strategy-factory", "status": "STALE", "critical": false, "age_hours": 745.24, "max_age_hours": 30.0, "timestamp_utc": "2026-09-02T13:06:16Z", "detail": "64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 745.2h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다."}, {"key": "autonomous-evolution", "status": "OK", "critical": false, "age_hours": 0.8, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T13:32:59Z", "detail": "영구 자율 성장 루프(스펙 067, 고레버리지 돌파 후보 보고 전용) — 신선(0.8h)."}, {"key": "autonomous-promotion", "status": "OK", "critical": false, "age_hours": 0.41, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T13:56:29Z", "detail": "자율 승격 루프(스펙 068, 후보→검증 단계 분류 보고 전용) — 신선(0.4h)."}, {"key": "candidate-implementation-factory", "status": "OK", "critical": false, "age_hours": 0.42, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T13:55:49Z", "detail": "후보 구현 공장(스펙 070, BACKTEST_REQUIRED 후보→검증 패키지) — 신선(0.4h)."}, {"key": "candidate-result-executor", "status": "OK", "critical": false, "age_hours": 0.4, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T13:56:39Z", "detail": "후보 결과 실행기(스펙 071, 검증 패키지→결과 evidence) — 신선(0.4h)."}, {"key": "autonomous-promotion-actions", "status": "OK", "critical": false, "age_hours": 0.24, "max_age_hours": 30.0, "timestamp_utc": "2026-10-03T14:06:45Z", "detail": "자율 승격 실행 루프(스펙 069, forward/canary 큐 연결) — 신선(0.2h)."}, {"key": "promotion-forward", "status": "OK", "critical": false, "age_hours": 12.9, "max_age_hours": 80.0, "timestamp_utc": "2026-10-03T01:27:05Z", "detail": "promotion 전용 forward paper 검증(스펙 069, paper only) — 신선(12.9h)."}, {"key": "promotion-canary", "status": "OK", "critical": false, "age_hours": 8.61, "max_age_hours": 80.0, "timestamp_utc": "2026-10-03T05:44:00Z", "detail": "promotion 전용 hardened canary 검증(스펙 069, live order 없음) — 신선(8.6h)."}, {"key": "reassign", "status": "OK", "critical": false, "age_hours": 8.91, "max_age_hours": 80.0, "timestamp_utc": "2026-10-03T05:26:11Z", "detail": "자율 전략 재지정 폐회로(스펙 055, 챔피언→라이브 5중 게이트) — 신선(8.9h)."}]}
```
