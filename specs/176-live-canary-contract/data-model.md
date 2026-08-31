# 데이터 모델: 증거 수렴형 실거래 검증 캐너리

## OperationalCanaryEvidence

장기 성과가 있는 기존 정확 배포 전략을 10% 운영 검증에 넣기 위한 불변 증거다.

| 필드 | 의미 |
|---|---|
| `schema_version` | 운영 증거 계약 버전 |
| `role` | 항상 `operational_canary_entry` |
| `route` | 항상 `historical-operational-canary-v1` |
| `code_commit` | 증거를 만든 40자리 Git 커밋 |
| `generated_at_utc` | 생성 시각 |
| `candidate_id` | 정확 배포 후보 ID |
| `strategy_fingerprint` | 라이브 설정의 SHA-256 |
| `data_fingerprint` | 원시 입력과 분할의 SHA-256 |
| `split` | 개발·홀드아웃 월 수와 겹침 수 |
| `cost_model` | 기본 50bp 이상과 진단 100/150bp |
| `holdout` | 월 목록, 후보·기준 원시 월별 요인, 재현 성과 |
| `checks` | 시간 분리·성과·지문·강화·대리·구현성 판정 |
| `diagnostics` | 초과수익 PSR과 비용 민감도, `alpha_confirmed:false` |
| `decision` | 운영 자격, 10% 자본, 최대 단 1, 20% 승격 불가 |
| `safety` | 주문 0건, 자본 변경 없음, 라이브 설정 변경 없음 |

## OperationalCanaryAssessment

자본 판정기가 증거를 독립 검증한 결과다.

- `checks`: 계약·역할·신선도·계보·지문·원시 숫자·위험 게이트별 불리언
- `recomputed`: 원시 요인에서 다시 계산한 CAGR·샤프·낙폭·PSR·비용 민감도
- `eligible`: 모든 운영 검증 조건의 논리곱
- `alpha_confirmed`: 항상 거짓
- `capital_fraction`: 자격 참이면 0.10, 아니면 0
- `max_rung`: 자격 참이어도 1
- `reasons`: 실패 폐쇄 원인 목록

## CapitalLadderSentinel

```text
DISARMED (rung 0, entry_route none)
  ├─ operational evidence ready ─> OPERATIONAL_CANARY (rung 1, 10%)
  ├─ factory research eligible ──> RESEARCH_CANARY (rung 1, 10%)
  └─ calibrated exploration ─────> EXPLORATION (rung 2, 20%)

OPERATIONAL_CANARY
  ├─ clean forward alpha gate ───> EXPLORATION (rung 2, 20%)
  ├─ safety failure ─────────────> DISARMED (rung 0)
  └─ live time alone ────────────> OPERATIONAL_CANARY (rung 1 유지)
```

추가 필드 `entry_route`는 `operational_canary`, `factory_research`, `exploration` 중 하나이며,
단수와 함께 자본 진입 근거를 보존한다.

## FirstOrderRevalidation

첫 실제 매수 직전에 만드는 판정이다.

- 증거 역할·신선도·커밋 계보
- 정확 후보 ID·전략 지문·데이터 지문
- 강화 검사와 체결 대리 등가성
- 최신 NAV 10% 정수 주 구현성
- 센티넬 단 1·`entry_route=operational_canary`
- KIS 계좌 정합·halt·킬스위치·정규장
- 기존 체결이 있으면 위험 축소 주문을 막지 않는 별도 분기

## LiveExecutionEvidence

한 예약 실행의 주문·체결·정합·감사를 연결한다.

- `run_id`, `code_commit`, `started_at_utc`, `market_session`
- `sentinel`, `capital_limit`, `account_nav`
- 정화된 주문 요청과 브로커 응답
- 체결 ID·수량·가격·수수료·시각
- 주문 전후 관리 포지션과 비관리 외부 보유
- 전략 장부 동기화 결과
- 계좌 정합 결과와 불일치 사유
- 감사 장부 위치와 sidecar 실행 ID

## LiveOrderSessionGate

실주문 진입점이 실제 실행 시각으로 만드는 일회성 판정이다.

- `mode`, `dry_run`: 실제 돈을 움직이는 호출인지 구분
- `checked_at_utc`: 서버가 검사한 현재 UTC 시각
- `XNYS regular session open`: 거래소 정규장 여부
- `next_open_utc`: 닫힌 장에서 운영 진단에 남길 다음 개장 시각
- 닫힌 장의 결과: 주문·브로커 조회·DB 마이그레이션 0건, 종료 코드 75
- 종이매매·미리보기: 판정 대상이 아니므로 기존 동작 유지
