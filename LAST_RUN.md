# 파이프라인 생존 감시 (as of 2026-09-05T12:47:48Z) — 읽기 전용, 돈 0 이동

종합 판정: 🟡 **DEGRADED**

| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |
|----------|:----:|:----:|--------:|--------:|-------------|
| rebalance-paper-forward | ✔ | 🟢 OK | 12.5 | 80 | 2026-09-05T00:19:17Z |
| edge-autoarm | ✔ | 🟢 OK | 10.6 | 80 | 2026-09-05T02:10:58Z |
| kis-smoke | ✔ | 🟢 OK | 5.3 | 30 | 2026-09-05T07:28:24Z |
| rebalance-live-canary | ✔ | 🟢 OK | 10.3 | 80 | 2026-09-05T02:30:39Z |
| collect-public-data |  | 🟢 OK | 6.8 | 80 | 2026-09-05T06:01:53Z |
| regime-stratify |  | 🟢 OK | 11.5 | 80 | 2026-09-05T01:18:10Z |
| regime-challenger-forward |  | 🟢 OK | 141.9 | 840 | 2026-08-30T14:55:42Z |
| promote-readiness |  | 🟢 OK | 12.6 | 30 | 2026-09-05T00:12:59Z |
| money-path |  | 🟢 OK | 1.2 | 30 | 2026-09-05T11:36:57Z |
| capital-path-readiness |  | 🟢 OK | 1.0 | 30 | 2026-09-05T11:49:03Z |
| autonomous-work-execution |  | 🟢 OK | 0.1 | 30 | 2026-09-05T12:38:50Z |
| released-work |  | 🟢 OK | 0.3 | 30 | 2026-09-05T12:28:59.210438Z |
| operator-status |  | 🟢 OK | 0.0 | 30 | 2026-09-05T12:47:28.422129Z |
| money-gate-alignment |  | 🟢 OK | 0.0 | 30 | 2026-09-05T12:46:10Z |
| execution-quality |  | 🟢 OK | 5.3 | 30 | 2026-09-05T07:28:43Z |
| profit-evidence-engine |  | 🟢 OK | 0.2 | 30 | 2026-09-05T12:38:44Z |
| autonomous-strategy-factory |  | 🔴 STALE | 71.7 | 30 | 2026-09-02T13:06:16Z |
| autonomous-evolution |  | 🟢 OK | 0.9 | 30 | 2026-09-05T11:52:55Z |
| autonomous-promotion |  | 🟢 OK | 0.7 | 30 | 2026-09-05T12:06:59Z |
| candidate-implementation-factory |  | 🟢 OK | 0.7 | 30 | 2026-09-05T12:05:46Z |
| candidate-result-executor |  | 🟢 OK | 0.7 | 30 | 2026-09-05T12:04:18Z |
| autonomous-promotion-actions |  | 🟢 OK | 0.5 | 30 | 2026-09-05T12:17:48Z |
| promotion-forward |  | 🟢 OK | 12.4 | 80 | 2026-09-05T00:23:15Z |
| promotion-canary |  | 🟢 OK | 7.9 | 80 | 2026-09-05T04:55:44Z |
| reassign |  | 🟢 OK | 8.2 | 80 | 2026-09-05T04:37:11Z |

- **autonomous-strategy-factory** (STALE): 64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 71.7h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다.

⚠ 이건 감시 보고다(읽기 전용). 거래·자본 변경 없음 — 라이브는 운영자 게이트(헌법 X.4).

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 4a5f43add677155382487f23a8a47debd2daa378 |
| trigger | workflow_run |
| timestamp_utc | 2026-09-05T12:47:48Z |

## 결정 JSON

```json
{"schema_version": "1.0", "as_of_utc": "2026-09-05T12:47:48Z", "overall": "DEGRADED", "checks": [{"key": "rebalance-paper-forward", "status": "OK", "critical": true, "age_hours": 12.48, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T00:19:17Z", "detail": "전진 페이퍼 A/B 토너먼트(전진 엣지 관측 생산) — 신선(12.5h)."}, {"key": "edge-autoarm", "status": "OK", "critical": true, "age_hours": 10.61, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T02:10:58Z", "detail": "자본 사다리 게이트(단 승격/강등 결정) — 신선(10.6h)."}, {"key": "kis-smoke", "status": "OK", "critical": true, "age_hours": 5.32, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T07:28:24Z", "detail": "KIS 브로커 연결 생존(매일) — 신선(5.3h)."}, {"key": "rebalance-live-canary", "status": "OK", "critical": true, "age_hours": 10.29, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T02:30:39Z", "detail": "라이브 캐너리 + 라이브 NAV 스냅샷 — 신선(10.3h)."}, {"key": "collect-public-data", "status": "OK", "critical": false, "age_hours": 6.77, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T06:01:53Z", "detail": "공개 데이터 수집·교차검증(연구 전용) — 신선(6.8h)."}, {"key": "regime-stratify", "status": "OK", "critical": false, "age_hours": 11.49, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T01:18:10Z", "detail": "레짐 층화(연구 전용) — 신선(11.5h)."}, {"key": "regime-challenger-forward", "status": "OK", "critical": false, "age_hours": 141.87, "max_age_hours": 840.0, "timestamp_utc": "2026-08-30T14:55:42Z", "detail": "7/8 레짐 후보 동결 후 월별 관찰(주문 없는 연구 전용) — 신선(141.9h)."}, {"key": "promote-readiness", "status": "OK", "critical": false, "age_hours": 12.58, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T00:12:59Z", "detail": "풀라이브 승격 준비 평가(보고 전용) — 신선(12.6h)."}, {"key": "money-path", "status": "OK", "critical": false, "age_hours": 1.18, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T11:36:57Z", "detail": "첫-자본까지의 길 종합·ETA(스펙 052, 보고 전용) — 신선(1.2h)."}, {"key": "capital-path-readiness", "status": "OK", "critical": false, "age_hours": 0.98, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T11:49:03Z", "detail": "자본 경로 준비도 루프(스펙 076, 보고 전용) — 신선(1.0h)."}, {"key": "autonomous-work-execution", "status": "OK", "critical": false, "age_hours": 0.15, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:38:50Z", "detail": "자율 작업 실행 루프(스펙 077, 다음 작업 패킷 보고 전용) — 신선(0.1h)."}, {"key": "released-work", "status": "OK", "critical": false, "age_hours": 0.31, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:28:59.210438Z", "detail": "완료 후보 소비 장부(스펙 079, 보고 전용) — 신선(0.3h)."}, {"key": "operator-status", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:47:28.422129Z", "detail": "운영자 상태 보고와 모바일 알림 루프(스펙 080, 보고 전용) — 신선(0.0h)."}, {"key": "money-gate-alignment", "status": "OK", "critical": false, "age_hours": 0.03, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:46:10Z", "detail": "돈 경로 게이트 정렬 루프(스펙 078, 보고 전용) — 신선(0.0h)."}, {"key": "execution-quality", "status": "OK", "critical": false, "age_hours": 5.32, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T07:28:43Z", "detail": "주문 거부·체결 품질 패키지(스펙 083, 보고 전용) — 신선(5.3h)."}, {"key": "profit-evidence-engine", "status": "OK", "critical": false, "age_hours": 0.15, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:38:44Z", "detail": "시간 분리·비용 차감 수익 후보 검증(스펙 138, 연구 전용) — 신선(0.2h)."}, {"key": "autonomous-strategy-factory", "status": "STALE", "critical": false, "age_hours": 71.69, "max_age_hours": 30.0, "timestamp_utc": "2026-09-02T13:06:16Z", "detail": "64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 71.7h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다."}, {"key": "autonomous-evolution", "status": "OK", "critical": false, "age_hours": 0.91, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T11:52:55Z", "detail": "영구 자율 성장 루프(스펙 067, 고레버리지 돌파 후보 보고 전용) — 신선(0.9h)."}, {"key": "autonomous-promotion", "status": "OK", "critical": false, "age_hours": 0.68, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:06:59Z", "detail": "자율 승격 루프(스펙 068, 후보→검증 단계 분류 보고 전용) — 신선(0.7h)."}, {"key": "candidate-implementation-factory", "status": "OK", "critical": false, "age_hours": 0.7, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:05:46Z", "detail": "후보 구현 공장(스펙 070, BACKTEST_REQUIRED 후보→검증 패키지) — 신선(0.7h)."}, {"key": "candidate-result-executor", "status": "OK", "critical": false, "age_hours": 0.73, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:04:18Z", "detail": "후보 결과 실행기(스펙 071, 검증 패키지→결과 evidence) — 신선(0.7h)."}, {"key": "autonomous-promotion-actions", "status": "OK", "critical": false, "age_hours": 0.5, "max_age_hours": 30.0, "timestamp_utc": "2026-09-05T12:17:48Z", "detail": "자율 승격 실행 루프(스펙 069, forward/canary 큐 연결) — 신선(0.5h)."}, {"key": "promotion-forward", "status": "OK", "critical": false, "age_hours": 12.41, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T00:23:15Z", "detail": "promotion 전용 forward paper 검증(스펙 069, paper only) — 신선(12.4h)."}, {"key": "promotion-canary", "status": "OK", "critical": false, "age_hours": 7.87, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T04:55:44Z", "detail": "promotion 전용 hardened canary 검증(스펙 069, live order 없음) — 신선(7.9h)."}, {"key": "reassign", "status": "OK", "critical": false, "age_hours": 8.18, "max_age_hours": 80.0, "timestamp_utc": "2026-09-05T04:37:11Z", "detail": "자율 전략 재지정 폐회로(스펙 055, 챔피언→라이브 5중 게이트) — 신선(8.2h)."}]}
```
