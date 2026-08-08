# 파이프라인 생존 감시 (as of 2026-08-08T09:57:40Z) — 읽기 전용, 돈 0 이동

종합 판정: 🟢 **OK**

| 사이드카 | 핵심 | 상태 | 나이(h) | 한계(h) | 마지막 갱신 |
|----------|:----:|:----:|--------:|--------:|-------------|
| rebalance-paper-forward | ✔ | 🟢 OK | 10.8 | 80 | 2026-08-07T23:09:50Z |
| edge-autoarm | ✔ | 🟢 OK | 9.4 | 80 | 2026-08-08T00:32:12Z |
| kis-smoke | ✔ | 🟢 OK | 5.8 | 30 | 2026-08-08T04:10:45Z |
| rebalance-live-canary | ✔ | 🟢 OK | 18.0 | 80 | 2026-08-07T15:59:51Z |
| collect-public-data |  | 🟢 OK | 6.8 | 80 | 2026-08-08T03:07:01Z |
| regime-stratify |  | 🟢 OK | 10.0 | 80 | 2026-08-08T00:00:10Z |
| promote-readiness |  | 🟢 OK | 10.9 | 30 | 2026-08-07T23:02:11Z |
| money-path |  | 🟢 OK | 1.3 | 30 | 2026-08-08T08:36:56Z |
| capital-path-readiness |  | 🟢 OK | 1.0 | 30 | 2026-08-08T08:57:18Z |
| autonomous-work-execution |  | 🟢 OK | 0.1 | 30 | 2026-08-08T09:51:19Z |
| released-work |  | 🟢 OK | 0.3 | 30 | 2026-08-08T09:41:01.663164Z |
| operator-status |  | 🟢 OK | 0.0 | 30 | 2026-08-08T09:57:16.439244Z |
| money-gate-alignment |  | 🟢 OK | 0.0 | 30 | 2026-08-08T09:56:19Z |
| execution-quality |  | 🟢 OK | 5.8 | 30 | 2026-08-08T04:11:00Z |
| autonomous-evolution |  | 🟢 OK | 0.8 | 30 | 2026-08-08T09:06:55Z |
| autonomous-promotion |  | 🟢 OK | 0.6 | 30 | 2026-08-08T09:21:50Z |
| candidate-implementation-factory |  | 🟢 OK | 0.6 | 30 | 2026-08-08T09:21:44Z |
| candidate-result-executor |  | 🟢 OK | 0.6 | 30 | 2026-08-08T09:21:04Z |
| autonomous-promotion-actions |  | 🟢 OK | 0.4 | 30 | 2026-08-08T09:32:04Z |
| promotion-forward |  | 🟢 OK | 10.7 | 80 | 2026-08-07T23:16:19Z |
| promotion-canary |  | 🟢 OK | 7.4 | 80 | 2026-08-08T02:34:17Z |
| reassign |  | 🟢 OK | 7.6 | 80 | 2026-08-08T02:24:12Z |


🟢 모든 핵심 사이드카 신선 — 자율 파이프라인 정상 가동.

⚠ 이건 감시 보고다(읽기 전용). 거래·자본 변경 없음 — 라이브는 운영자 게이트(헌법 X.4).

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | workflow_run |
| timestamp_utc | 2026-08-08T09:57:40Z |

## 결정 JSON

```json
{"schema_version": "1.0", "as_of_utc": "2026-08-08T09:57:40Z", "overall": "OK", "checks": [{"key": "rebalance-paper-forward", "status": "OK", "critical": true, "age_hours": 10.8, "max_age_hours": 80.0, "timestamp_utc": "2026-08-07T23:09:50Z", "detail": "전진 페이퍼 A/B 토너먼트(전진 엣지 관측 생산) — 신선(10.8h)."}, {"key": "edge-autoarm", "status": "OK", "critical": true, "age_hours": 9.42, "max_age_hours": 80.0, "timestamp_utc": "2026-08-08T00:32:12Z", "detail": "자본 사다리 게이트(단 승격/강등 결정) — 신선(9.4h)."}, {"key": "kis-smoke", "status": "OK", "critical": true, "age_hours": 5.78, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T04:10:45Z", "detail": "KIS 브로커 연결 생존(매일) — 신선(5.8h)."}, {"key": "rebalance-live-canary", "status": "OK", "critical": true, "age_hours": 17.96, "max_age_hours": 80.0, "timestamp_utc": "2026-08-07T15:59:51Z", "detail": "라이브 캐너리 + 라이브 NAV 스냅샷 — 신선(18.0h)."}, {"key": "collect-public-data", "status": "OK", "critical": false, "age_hours": 6.84, "max_age_hours": 80.0, "timestamp_utc": "2026-08-08T03:07:01Z", "detail": "공개 데이터 수집·교차검증(연구 전용) — 신선(6.8h)."}, {"key": "regime-stratify", "status": "OK", "critical": false, "age_hours": 9.96, "max_age_hours": 80.0, "timestamp_utc": "2026-08-08T00:00:10Z", "detail": "레짐 층화(연구 전용) — 신선(10.0h)."}, {"key": "promote-readiness", "status": "OK", "critical": false, "age_hours": 10.92, "max_age_hours": 30.0, "timestamp_utc": "2026-08-07T23:02:11Z", "detail": "풀라이브 승격 준비 평가(보고 전용) — 신선(10.9h)."}, {"key": "money-path", "status": "OK", "critical": false, "age_hours": 1.35, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T08:36:56Z", "detail": "첫-자본까지의 길 종합·ETA(스펙 052, 보고 전용) — 신선(1.3h)."}, {"key": "capital-path-readiness", "status": "OK", "critical": false, "age_hours": 1.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T08:57:18Z", "detail": "자본 경로 준비도 루프(스펙 076, 보고 전용) — 신선(1.0h)."}, {"key": "autonomous-work-execution", "status": "OK", "critical": false, "age_hours": 0.11, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:51:19Z", "detail": "자율 작업 실행 루프(스펙 077, 다음 작업 패킷 보고 전용) — 신선(0.1h)."}, {"key": "released-work", "status": "OK", "critical": false, "age_hours": 0.28, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:41:01.663164Z", "detail": "완료 후보 소비 장부(스펙 079, 보고 전용) — 신선(0.3h)."}, {"key": "operator-status", "status": "OK", "critical": false, "age_hours": 0.01, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:57:16.439244Z", "detail": "운영자 상태 보고와 모바일 알림 루프(스펙 080, 보고 전용) — 신선(0.0h)."}, {"key": "money-gate-alignment", "status": "OK", "critical": false, "age_hours": 0.02, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:56:19Z", "detail": "돈 경로 게이트 정렬 루프(스펙 078, 보고 전용) — 신선(0.0h)."}, {"key": "execution-quality", "status": "OK", "critical": false, "age_hours": 5.78, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T04:11:00Z", "detail": "주문 거부·체결 품질 패키지(스펙 083, 보고 전용) — 신선(5.8h)."}, {"key": "autonomous-evolution", "status": "OK", "critical": false, "age_hours": 0.85, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:06:55Z", "detail": "영구 자율 성장 루프(스펙 067, 고레버리지 돌파 후보 보고 전용) — 신선(0.8h)."}, {"key": "autonomous-promotion", "status": "OK", "critical": false, "age_hours": 0.6, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:21:50Z", "detail": "자율 승격 루프(스펙 068, 후보→검증 단계 분류 보고 전용) — 신선(0.6h)."}, {"key": "candidate-implementation-factory", "status": "OK", "critical": false, "age_hours": 0.6, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:21:44Z", "detail": "후보 구현 공장(스펙 070, BACKTEST_REQUIRED 후보→검증 패키지) — 신선(0.6h)."}, {"key": "candidate-result-executor", "status": "OK", "critical": false, "age_hours": 0.61, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:21:04Z", "detail": "후보 결과 실행기(스펙 071, 검증 패키지→결과 evidence) — 신선(0.6h)."}, {"key": "autonomous-promotion-actions", "status": "OK", "critical": false, "age_hours": 0.43, "max_age_hours": 30.0, "timestamp_utc": "2026-08-08T09:32:04Z", "detail": "자율 승격 실행 루프(스펙 069, forward/canary 큐 연결) — 신선(0.4h)."}, {"key": "promotion-forward", "status": "OK", "critical": false, "age_hours": 10.69, "max_age_hours": 80.0, "timestamp_utc": "2026-08-07T23:16:19Z", "detail": "promotion 전용 forward paper 검증(스펙 069, paper only) — 신선(10.7h)."}, {"key": "promotion-canary", "status": "OK", "critical": false, "age_hours": 7.39, "max_age_hours": 80.0, "timestamp_utc": "2026-08-08T02:34:17Z", "detail": "promotion 전용 hardened canary 검증(스펙 069, live order 없음) — 신선(7.4h)."}, {"key": "reassign", "status": "OK", "critical": false, "age_hours": 7.56, "max_age_hours": 80.0, "timestamp_utc": "2026-08-08T02:24:12Z", "detail": "자율 전략 재지정 폐회로(스펙 055, 챔피언→라이브 5중 게이트) — 신선(7.6h)."}]}
```
