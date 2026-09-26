# 파이프라인 생존 감시 (as of 2026-09-26T13:47:32Z) — 읽기 전용, 돈 0 이동

종합 판정: 🟡 **DEGRADED**

| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |
|----------|:----:|:----:|--------:|--------:|-------------|
| rebalance-paper-forward | ✔ | 🟢 OK | 13.0 | 80 | 2026-09-26T00:49:17Z |
| edge-autoarm | ✔ | 🟢 OK | 11.7 | 80 | 2026-09-26T02:04:26Z |
| kis-smoke | ✔ | 🟢 OK | 5.4 | 30 | 2026-09-26T08:24:44Z |
| rebalance-live-canary | ✔ | 🟢 OK | 19.1 | 80 | 2026-09-25T18:40:46Z |
| collect-public-data |  | 🟢 OK | 7.5 | 80 | 2026-09-26T06:19:24Z |
| regime-stratify |  | 🟢 OK | 11.9 | 80 | 2026-09-26T01:50:50Z |
| regime-challenger-forward |  | 🟢 OK | 241.1 | 840 | 2026-09-16T12:39:54Z |
| promote-readiness |  | 🟢 OK | 13.1 | 30 | 2026-09-26T00:43:18Z |
| money-path |  | 🟢 OK | 1.1 | 30 | 2026-09-26T12:39:54Z |
| capital-path-readiness |  | 🟢 OK | 0.8 | 30 | 2026-09-26T13:01:53Z |
| autonomous-work-execution |  | 🟢 OK | 0.1 | 30 | 2026-09-26T13:43:43Z |
| released-work |  | 🟢 OK | 0.1 | 30 | 2026-09-26T13:39:55.138310Z |
| operator-status |  | 🟢 OK | 0.0 | 30 | 2026-09-26T13:46:39.081040Z |
| money-gate-alignment |  | 🟢 OK | 0.0 | 30 | 2026-09-26T13:46:05Z |
| execution-quality |  | 🟢 OK | 5.4 | 30 | 2026-09-26T08:25:00Z |
| profit-evidence-engine |  | 🟢 OK | 0.1 | 30 | 2026-09-26T13:43:41Z |
| autonomous-strategy-factory |  | 🔴 STALE | 576.7 | 30 | 2026-09-02T13:06:16Z |
| autonomous-evolution |  | 🟢 OK | 0.5 | 30 | 2026-09-26T13:15:09Z |
| autonomous-promotion |  | 🟢 OK | 0.4 | 30 | 2026-09-26T13:23:41Z |
| candidate-implementation-factory |  | 🟢 OK | 0.4 | 30 | 2026-09-26T13:23:12Z |
| candidate-result-executor |  | 🟢 OK | 0.4 | 30 | 2026-09-26T13:23:08Z |
| autonomous-promotion-actions |  | 🟢 OK | 0.2 | 30 | 2026-09-26T13:34:55Z |
| promotion-forward |  | 🟢 OK | 12.9 | 80 | 2026-09-26T00:52:44Z |
| promotion-canary |  | 🟢 OK | 8.3 | 80 | 2026-09-26T05:28:18Z |
| reassign |  | 🟢 OK | 8.7 | 80 | 2026-09-26T05:07:37Z |

- **autonomous-strategy-factory** (STALE): 64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 576.7h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다.

⚠ 이건 감시 보고다(읽기 전용). 거래·자본 변경 없음 — 라이브는 운영자 게이트(헌법 X.4).

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 37829096639c7ef60c3df43bf899fce516667fc4 |
| trigger | workflow_run |
| timestamp_utc | 2026-09-26T13:47:32Z |

## 결정 JSON

```json
{"schema_version": "1.0", "as_of_utc": "2026-09-26T13:47:32Z", "overall": "DEGRADED", "checks": [{"key": "rebalance-paper-forward", "status": "OK", "critical": true, "age_hours": 12.97, "max_age_hours": 80.0, "timestamp_utc": "2026-09-26T00:49:17Z", "detail": "전진 페이퍼 A/B 토너먼트(전진 엣지 관측 생산) — 신선(13.0h)."}, {"key": "edge-autoarm", "status": "OK", "critical": true, "age_hours": 11.72, "max_age_hours": 80.0, "timestamp_utc": "2026-09-26T02:04:26Z", "detail": "자본 사다리 게이트(단 승격/강등 결정) — 신선(11.7h)."}, {"key": "kis-smoke", "status": "OK", "critical": true, "age_hours": 5.38, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T08:24:44Z", "detail": "KIS 브로커 연결 생존(매일) — 신선(5.4h)."}, {"key": "rebalance-live-canary", "status": "OK", "critical": true, "age_hours": 19.11, "max_age_hours": 80.0, "timestamp_utc": "2026-09-25T18:40:46Z", "detail": "라이브 캐너리 + 라이브 NAV 스냅샷 — 신선(19.1h)."}, {"key": "collect-public-data", "status": "OK", "critical": false, "age_hours": 7.47, "max_age_hours": 80.0, "timestamp_utc": "2026-09-26T06:19:24Z", "detail": "공개 데이터 수집·교차검증(연구 전용) — 신선(7.5h)."}, {"key": "regime-stratify", "status": "OK", "critical": false, "age_hours": 11.95, "max_age_hours": 80.0, "timestamp_utc": "2026-09-26T01:50:50Z", "detail": "레짐 층화(연구 전용) — 신선(11.9h)."}, {"key": "regime-challenger-forward", "status": "OK", "critical": false, "age_hours": 241.13, "max_age_hours": 840.0, "timestamp_utc": "2026-09-16T12:39:54Z", "detail": "7/8 레짐 후보 동결 후 월별 관찰(주문 없는 연구 전용) — 신선(241.1h)."}, {"key": "promote-readiness", "status": "OK", "critical": false, "age_hours": 13.07, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T00:43:18Z", "detail": "풀라이브 승격 준비 평가(보고 전용) — 신선(13.1h)."}, {"key": "money-path", "status": "OK", "critical": false, "age_hours": 1.13, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T12:39:54Z", "detail": "첫-자본까지의 길 종합·ETA(스펙 052, 보고 전용) — 신선(1.1h)."}, {"key": "capital-path-readiness", "status": "OK", "critical": false, "age_hours": 0.76, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:01:53Z", "detail": "자본 경로 준비도 루프(스펙 076, 보고 전용) — 신선(0.8h)."}, {"key": "autonomous-work-execution", "status": "OK", "critical": false, "age_hours": 0.06, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:43:43Z", "detail": "자율 작업 실행 루프(스펙 077, 다음 작업 패킷 보고 전용) — 신선(0.1h)."}, {"key": "released-work", "status": "OK", "critical": false, "age_hours": 0.13, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:39:55.138310Z", "detail": "완료 후보 소비 장부(스펙 079, 보고 전용) — 신선(0.1h)."}, {"key": "operator-status", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:46:39.081040Z", "detail": "운영자 상태 보고와 모바일 알림 루프(스펙 080, 보고 전용) — 신선(0.0h)."}, {"key": "money-gate-alignment", "status": "OK", "critical": false, "age_hours": 0.02, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:46:05Z", "detail": "돈 경로 게이트 정렬 루프(스펙 078, 보고 전용) — 신선(0.0h)."}, {"key": "execution-quality", "status": "OK", "critical": false, "age_hours": 5.38, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T08:25:00Z", "detail": "주문 거부·체결 품질 패키지(스펙 083, 보고 전용) — 신선(5.4h)."}, {"key": "profit-evidence-engine", "status": "OK", "critical": false, "age_hours": 0.06, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:43:41Z", "detail": "시간 분리·비용 차감 수익 후보 검증(스펙 138, 연구 전용) — 신선(0.1h)."}, {"key": "autonomous-strategy-factory", "status": "STALE", "critical": false, "age_hours": 576.69, "max_age_hours": 30.0, "timestamp_utc": "2026-09-02T13:06:16Z", "detail": "64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 576.7h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다."}, {"key": "autonomous-evolution", "status": "OK", "critical": false, "age_hours": 0.54, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:15:09Z", "detail": "영구 자율 성장 루프(스펙 067, 고레버리지 돌파 후보 보고 전용) — 신선(0.5h)."}, {"key": "autonomous-promotion", "status": "OK", "critical": false, "age_hours": 0.4, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:23:41Z", "detail": "자율 승격 루프(스펙 068, 후보→검증 단계 분류 보고 전용) — 신선(0.4h)."}, {"key": "candidate-implementation-factory", "status": "OK", "critical": false, "age_hours": 0.41, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:23:12Z", "detail": "후보 구현 공장(스펙 070, BACKTEST_REQUIRED 후보→검증 패키지) — 신선(0.4h)."}, {"key": "candidate-result-executor", "status": "OK", "critical": false, "age_hours": 0.41, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:23:08Z", "detail": "후보 결과 실행기(스펙 071, 검증 패키지→결과 evidence) — 신선(0.4h)."}, {"key": "autonomous-promotion-actions", "status": "OK", "critical": false, "age_hours": 0.21, "max_age_hours": 30.0, "timestamp_utc": "2026-09-26T13:34:55Z", "detail": "자율 승격 실행 루프(스펙 069, forward/canary 큐 연결) — 신선(0.2h)."}, {"key": "promotion-forward", "status": "OK", "critical": false, "age_hours": 12.91, "max_age_hours": 80.0, "timestamp_utc": "2026-09-26T00:52:44Z", "detail": "promotion 전용 forward paper 검증(스펙 069, paper only) — 신선(12.9h)."}, {"key": "promotion-canary", "status": "OK", "critical": false, "age_hours": 8.32, "max_age_hours": 80.0, "timestamp_utc": "2026-09-26T05:28:18Z", "detail": "promotion 전용 hardened canary 검증(스펙 069, live order 없음) — 신선(8.3h)."}, {"key": "reassign", "status": "OK", "critical": false, "age_hours": 8.67, "max_age_hours": 80.0, "timestamp_utc": "2026-09-26T05:07:37Z", "detail": "자율 전략 재지정 폐회로(스펙 055, 챔피언→라이브 5중 게이트) — 신선(8.7h)."}]}
```
