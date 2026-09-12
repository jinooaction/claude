# 파이프라인 생존 감시 (as of 2026-09-12T12:55:28Z) — 읽기 전용, 돈 0 이동

종합 판정: 🟡 **DEGRADED**

| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |
|----------|:----:|:----:|--------:|--------:|-------------|
| rebalance-paper-forward | ✔ | 🟢 OK | 12.4 | 80 | 2026-09-12T00:31:11Z |
| edge-autoarm | ✔ | 🟢 OK | 11.3 | 80 | 2026-09-12T01:37:12Z |
| kis-smoke | ✔ | 🟢 OK | 1.2 | 30 | 2026-09-12T11:42:45Z |
| rebalance-live-canary | ✔ | 🟢 OK | 18.5 | 80 | 2026-09-11T18:27:32Z |
| collect-public-data |  | 🟢 OK | 6.8 | 80 | 2026-09-12T06:05:57Z |
| regime-stratify |  | 🟢 OK | 11.5 | 80 | 2026-09-12T01:24:05Z |
| regime-challenger-forward |  | 🟢 OK | 310.0 | 840 | 2026-08-30T14:55:42Z |
| promote-readiness |  | 🟢 OK | 12.5 | 30 | 2026-09-12T00:25:06Z |
| money-path |  | 🟢 OK | 1.0 | 30 | 2026-09-12T11:57:29Z |
| capital-path-readiness |  | 🟢 OK | 0.8 | 30 | 2026-09-12T12:08:44Z |
| autonomous-work-execution |  | 🟢 OK | 0.1 | 30 | 2026-09-12T12:49:39Z |
| released-work |  | 🟢 OK | 0.2 | 30 | 2026-09-12T12:43:58.693697Z |
| operator-status |  | 🟢 OK | 0.0 | 30 | 2026-09-12T12:55:08.351677Z |
| money-gate-alignment |  | 🟢 OK | 0.0 | 30 | 2026-09-12T12:53:48Z |
| execution-quality |  | 🟢 OK | 1.2 | 30 | 2026-09-12T11:43:02Z |
| profit-evidence-engine |  | 🟢 OK | 0.1 | 30 | 2026-09-12T12:49:42Z |
| autonomous-strategy-factory |  | 🔴 STALE | 239.8 | 30 | 2026-09-02T13:06:16Z |
| autonomous-evolution |  | 🟢 OK | 0.7 | 30 | 2026-09-12T12:14:45Z |
| autonomous-promotion |  | 🟢 OK | 0.5 | 30 | 2026-09-12T12:22:36Z |
| candidate-implementation-factory |  | 🟢 OK | 0.6 | 30 | 2026-09-12T12:22:08Z |
| candidate-result-executor |  | 🟢 OK | 0.6 | 30 | 2026-09-12T12:21:55Z |
| autonomous-promotion-actions |  | 🟢 OK | 0.3 | 30 | 2026-09-12T12:34:56Z |
| promotion-forward |  | 🟢 OK | 12.3 | 80 | 2026-09-12T00:38:23Z |
| promotion-canary |  | 🟢 OK | 7.9 | 80 | 2026-09-12T05:01:26Z |
| reassign |  | 🟢 OK | 8.2 | 80 | 2026-09-12T04:42:24Z |

- **autonomous-strategy-factory** (STALE): 64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 239.8h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다.

⚠ 이건 감시 보고다(읽기 전용). 거래·자본 변경 없음 — 라이브는 운영자 게이트(헌법 X.4).

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | e79cb01dcc14415c42d515ec4e1a5fda932817b3 |
| trigger | workflow_run |
| timestamp_utc | 2026-09-12T12:55:28Z |

## 결정 JSON

```json
{"schema_version": "1.0", "as_of_utc": "2026-09-12T12:55:27Z", "overall": "DEGRADED", "checks": [{"key": "rebalance-paper-forward", "status": "OK", "critical": true, "age_hours": 12.4, "max_age_hours": 80.0, "timestamp_utc": "2026-09-12T00:31:11Z", "detail": "전진 페이퍼 A/B 토너먼트(전진 엣지 관측 생산) — 신선(12.4h)."}, {"key": "edge-autoarm", "status": "OK", "critical": true, "age_hours": 11.3, "max_age_hours": 80.0, "timestamp_utc": "2026-09-12T01:37:12Z", "detail": "자본 사다리 게이트(단 승격/강등 결정) — 신선(11.3h)."}, {"key": "kis-smoke", "status": "OK", "critical": true, "age_hours": 1.21, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T11:42:45Z", "detail": "KIS 브로커 연결 생존(매일) — 신선(1.2h)."}, {"key": "rebalance-live-canary", "status": "OK", "critical": true, "age_hours": 18.47, "max_age_hours": 80.0, "timestamp_utc": "2026-09-11T18:27:32Z", "detail": "라이브 캐너리 + 라이브 NAV 스냅샷 — 신선(18.5h)."}, {"key": "collect-public-data", "status": "OK", "critical": false, "age_hours": 6.83, "max_age_hours": 80.0, "timestamp_utc": "2026-09-12T06:05:57Z", "detail": "공개 데이터 수집·교차검증(연구 전용) — 신선(6.8h)."}, {"key": "regime-stratify", "status": "OK", "critical": false, "age_hours": 11.52, "max_age_hours": 80.0, "timestamp_utc": "2026-09-12T01:24:05Z", "detail": "레짐 층화(연구 전용) — 신선(11.5h)."}, {"key": "regime-challenger-forward", "status": "OK", "critical": false, "age_hours": 310.0, "max_age_hours": 840.0, "timestamp_utc": "2026-08-30T14:55:42Z", "detail": "7/8 레짐 후보 동결 후 월별 관찰(주문 없는 연구 전용) — 신선(310.0h)."}, {"key": "promote-readiness", "status": "OK", "critical": false, "age_hours": 12.51, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T00:25:06Z", "detail": "풀라이브 승격 준비 평가(보고 전용) — 신선(12.5h)."}, {"key": "money-path", "status": "OK", "critical": false, "age_hours": 0.97, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T11:57:29Z", "detail": "첫-자본까지의 길 종합·ETA(스펙 052, 보고 전용) — 신선(1.0h)."}, {"key": "capital-path-readiness", "status": "OK", "critical": false, "age_hours": 0.78, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:08:44Z", "detail": "자본 경로 준비도 루프(스펙 076, 보고 전용) — 신선(0.8h)."}, {"key": "autonomous-work-execution", "status": "OK", "critical": false, "age_hours": 0.1, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:49:39Z", "detail": "자율 작업 실행 루프(스펙 077, 다음 작업 패킷 보고 전용) — 신선(0.1h)."}, {"key": "released-work", "status": "OK", "critical": false, "age_hours": 0.19, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:43:58.693697Z", "detail": "완료 후보 소비 장부(스펙 079, 보고 전용) — 신선(0.2h)."}, {"key": "operator-status", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:55:08.351677Z", "detail": "운영자 상태 보고와 모바일 알림 루프(스펙 080, 보고 전용) — 신선(0.0h)."}, {"key": "money-gate-alignment", "status": "OK", "critical": false, "age_hours": 0.03, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:53:48Z", "detail": "돈 경로 게이트 정렬 루프(스펙 078, 보고 전용) — 신선(0.0h)."}, {"key": "execution-quality", "status": "OK", "critical": false, "age_hours": 1.21, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T11:43:02Z", "detail": "주문 거부·체결 품질 패키지(스펙 083, 보고 전용) — 신선(1.2h)."}, {"key": "profit-evidence-engine", "status": "OK", "critical": false, "age_hours": 0.1, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:49:42Z", "detail": "시간 분리·비용 차감 수익 후보 검증(스펙 138, 연구 전용) — 신선(0.1h)."}, {"key": "autonomous-strategy-factory", "status": "STALE", "critical": false, "age_hours": 239.82, "max_age_hours": 30.0, "timestamp_utc": "2026-09-02T13:06:16Z", "detail": "64개 후보 전체 다중검정 자동 전략 탐색(스펙 150, 연구 전용) — 239.8h 경과(한계 30h 의 2배 초과). 워크플로가 멈췄을 가능성이 높다."}, {"key": "autonomous-evolution", "status": "OK", "critical": false, "age_hours": 0.68, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:14:45Z", "detail": "영구 자율 성장 루프(스펙 067, 고레버리지 돌파 후보 보고 전용) — 신선(0.7h)."}, {"key": "autonomous-promotion", "status": "OK", "critical": false, "age_hours": 0.55, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:22:36Z", "detail": "자율 승격 루프(스펙 068, 후보→검증 단계 분류 보고 전용) — 신선(0.5h)."}, {"key": "candidate-implementation-factory", "status": "OK", "critical": false, "age_hours": 0.56, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:22:08Z", "detail": "후보 구현 공장(스펙 070, BACKTEST_REQUIRED 후보→검증 패키지) — 신선(0.6h)."}, {"key": "candidate-result-executor", "status": "OK", "critical": false, "age_hours": 0.56, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:21:55Z", "detail": "후보 결과 실행기(스펙 071, 검증 패키지→결과 evidence) — 신선(0.6h)."}, {"key": "autonomous-promotion-actions", "status": "OK", "critical": false, "age_hours": 0.34, "max_age_hours": 30.0, "timestamp_utc": "2026-09-12T12:34:56Z", "detail": "자율 승격 실행 루프(스펙 069, forward/canary 큐 연결) — 신선(0.3h)."}, {"key": "promotion-forward", "status": "OK", "critical": false, "age_hours": 12.28, "max_age_hours": 80.0, "timestamp_utc": "2026-09-12T00:38:23Z", "detail": "promotion 전용 forward paper 검증(스펙 069, paper only) — 신선(12.3h)."}, {"key": "promotion-canary", "status": "OK", "critical": false, "age_hours": 7.9, "max_age_hours": 80.0, "timestamp_utc": "2026-09-12T05:01:26Z", "detail": "promotion 전용 hardened canary 검증(스펙 069, live order 없음) — 신선(7.9h)."}, {"key": "reassign", "status": "OK", "critical": false, "age_hours": 8.22, "max_age_hours": 80.0, "timestamp_utc": "2026-09-12T04:42:24Z", "detail": "자율 전략 재지정 폐회로(스펙 055, 챔피언→라이브 5중 게이트) — 신선(8.2h)."}]}
```
