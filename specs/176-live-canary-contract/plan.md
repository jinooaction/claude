# 구현 계획: 증거 수렴형 실거래 검증 캐너리

**브랜치**: `Codex/176-live-canary-contract` | **작성일**: 2026-08-31  
**명세**: [spec.md](spec.md) | **위험 등급**: 4 - 실제 자본·주문 경로 변경

## 요약

장기 시간 분리 검증과 정확한 배포 지문을 통과한 기존 `globalfixed` 전략에 대해 실계좌 NAV의
10%까지만 운영 검증 캐너리를 허용한다. 이 상태는 주문·체결·감사·정합 배관을 검증하기 위한
것이며 확정 알파가 아니다. 20% 이상 승격은 기존 깨끗한 전진 표본·PSR·칼마·전체 경로 교정
요건을 그대로 유지한다. 연구 진단 결과와 자본 진입 증거는 별도 파일과 역할로 발행한다.

## 기술 배경

- **언어/런타임**: Python 3.11, Bash, GitHub Actions
- **주요 의존성**: NumPy, Pydantic, `exchange_calendars`, KIS REST 경계
- **상태 저장**: sidecar 브랜치의 추가 전용 JSON, 서버의 SQLite 주문·체결·감사 장부
- **실행 경로**: `Backtest -> 10% Operational Canary -> 20% Exploration -> Full`
- **주문 제약**: KIS production, 정수 주, 지정가, 미국 정규장, 서명·nonce, K1/K2
- **기본 검증**: `uv run pytest`, `uv run ruff check src tests`

## 헌법 점검

### 구현 전 관문

- K1 포지션 한도와 K2 허용 종목은 낮추지 않는다.
- 연 20% 손실 예산, 절반 하향, 전액 정지, 킬스위치를 유지한다.
- 비밀값은 GitHub Actions와 서버 비밀 경계 밖으로 노출하지 않는다.
- 주문·체결·오류 감사 로그는 추가 전용으로 유지한다.
- 외부 API 장애, 정합 불일치, 오래된 증거는 실패 폐쇄한다.
- 장중에는 배포하지 않고, 주문은 정규장 예약 실행만 사용한다.
- `Backtest -> Canary -> Full` 단계를 생략하지 않는다.
- 10% 운영 캐너리는 새 자본 진입 상태이므로 헌법 X.4를 별도 커밋으로 개정한다.

### 설계 후 관문

- 운영 검증 자격과 알파 승격 자격은 다른 필드와 파일로 분리된다.
- 운영 증거 소비자가 원시 월별 수익률을 재계산해 제작자의 자기 판정을 신뢰하지 않는다.
- 10% 운영 캐너리는 센티넬에 진입 출처를 기록하고, 그 출처만으로 20%에 오를 수 없다.
- 첫 매수 직전에 코드 커밋·전략 지문·강화 검사·체결 대리·정수 주·정합·halt를 재검사한다.
- 위험 축소 매도는 오래된 연구 증거 때문에 막히지 않는다.
- 실제 체결이 없으면 완료로 선언하지 않는다.

## 저장소 구조

### 명세 산출물

```text
specs/176-live-canary-contract/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── operational-canary-evidence.schema.json
└── tasks.md
```

### 구현 대상

```text
src/auto_invest/
├── analytics/
│   ├── profit_evidence_engine.py
│   └── money_path.py
├── portfolio/
│   ├── operational_canary_evidence.py
│   ├── capital_ladder.py
│   └── live_entry_revalidation.py
└── cli.py

scripts/
├── profit_evidence_engine_probe.py
├── operational_canary_evidence_gate.py
└── live_entry_revalidation_probe.py

.github/workflows/
├── profit-evidence-engine.yml
├── autonomous-strategy-factory.yml
├── forward-edge-autoarm.yml
└── rebalance-live-canary.yml
```

## 구현 순서

1. 명세·계획·과제와 계약을 먼저 커밋한다.
2. 헌법 X.4에 10% 운영 검증 캐너리를 추가하고 버전을 올려 전용 안전 경계 커밋을 만든다.
3. 운영 증거 검증, 역할 분리, 10% 진입, 20% 승격 차단, 첫 주문 재검사의 실패 테스트를 먼저 만든다.
4. 원시 월별 요인과 진단값을 포함한 운영 검증 증거 제작기·독립 검증기를 구현한다.
5. `strategy_factory.json`의 혼합 역할을 진단 파일과 `capital_entry_evidence.json`으로 분리한다.
6. 자본 사다리와 첫 주문 재검사기가 운영 증거를 명시적으로 소비하게 한다.
7. 센티넬에 `entry_route`를 기록하고 운영 경로가 단 1을 넘지 못하게 한다.
8. 전체 테스트·린트·엄격 하네스·HANDOFF 사실 검사·PR 품질 관문을 통과시킨다.
9. 커밋·푸시·PR·머지 뒤 main 배포와 sidecar 증거 발행을 확인한다.
10. 최신 NAV의 10%로 단 0에서 단 1까지 무장됐는지 확인한다.
11. 다음 미국 정규장 예약 실행에서 실제 주문·체결·정합·감사 기록을 확인한다.
12. 최종 운영 상태를 `HANDOFF.md`에 기록하고 다시 검증한다.
13. 실제 예약 지연 이력과 GitHub 공식 권고에 따라 라이브 캐너리만 뉴욕 현지 10:17 비정각
    예약으로 바꾸고, 운영 화면의 다음 실행 시각을 같은 계약으로 맞춘다.
14. 예약이 장 마감 뒤 도착해도 주문되지 않도록 `rebalance-once` 실주문 진입점이 서버 실제
    시각을 XNYS 달력으로 재검사하고, 닫힌 장에서는 DB·브로커 접근 전 실패 폐쇄하게 한다.

## 복잡성 정당화

| 선택 | 필요한 이유 | 더 단순한 선택이 실패하는 이유 |
|---|---|---|
| 자본 진입 증거를 연구 진단과 별도 파일로 발행 | 최신 진단이 자본 역할을 덮어쓰는 오류 제거 | 단일 파일은 서로 다른 신선도와 자격을 표현하지 못함 |
| 운영 증거에 원시 월별 요인을 포함 | 소비자가 성과와 PSR을 독립 재계산 | 제작자 불리언만 신뢰하면 계약 오류를 발견할 수 없음 |
| 센티넬에 `entry_route` 기록 | 운영 10%가 일반 승격 조건으로 20%에 오르는 것 차단 | 단수만 저장하면 자본 진입 근거를 잃음 |
| 뉴욕 현지 10:17 단일 예약 | 정각 혼잡과 서머타임 오차를 동시에 제거 | 15:00 UTC 정각은 실측상 장 마감 뒤까지 지연됐고, 여러 예약은 중복 주문 표면을 넓힘 |
| 실주문 CLI의 XNYS 재검사 | 예약 시각과 실제 시작 시각의 차이를 주문 직전 차단 | 예약 설정만 믿으면 9시간 지연 실행이 장 마감 뒤 KIS 주문을 시도함 |

## 롤백

센티넬을 `armed:false`, 단 0, 자본 0으로 내리고 기능 커밋을 되돌린다. 기존 주문·체결·감사
행은 삭제하지 않는다. 이미 산 보유분은 기존 위험 축소 경로로만 정리한다. 연구 진단과 과거
오염 장부는 포렌식 자료로 보존한다.
