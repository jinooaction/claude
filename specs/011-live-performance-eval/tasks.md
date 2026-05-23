# Tasks: 라이브 성과 측정 하네스 (spec 011)

상태 범례: [X] 완료 · [ ] 대기

## P1 — 손익 측정 엔진 + performance CLI (US1+US3) ✅ 완료

- [X] T001 성과 측정 엔진 `src/auto_invest/performance/engine.py` — 평균단가 기준
      실현 손익 재구성, 주입 시세 기반 미실현 손익, 투입 대비 수익률.
- [X] T002 라이브 FILL ↔ ORDER_INTENT side 조인 / 페이퍼 ORDER_PAPER_FILLED 읽기
      (`read_fills`, 모드 분리 FR-003).
- [X] T003 룰별·종목별 기여도 분해 (US3, 합산 보존 SC-003).
- [X] T004 시세 누락 시 우아한 강등 — 미실현 "조회 불가", 실현 정상 (FR-005).
- [X] T005 공매도/데이터 품질 경고, 빈 입력 N/A (FR-010).
- [X] T006 `auto-invest performance` CLI — `--mode`/`--format`/`--no-marks`,
      PRAGMA query_only 읽기 전용, KIS 시세 mark-to-market(`_fetch_marks`).
- [X] T007 JSON 출력 스키마 버전 (FR-011, 튜너 소비용).
- [X] T008 단위 테스트 13건 + CLI 통합 6건 (실현/미실현/합산보존/읽기전용/경계).

## P2 — 위험조정 성과 (US2) ✅ 완료

- [X] T009 일별 실현 손익 → 누적 자산곡선 재구성 (`realized_trades`,
      `compute_risk_metrics` 의 거래일별 equity 시계열).
- [X] T010 spec 008 `backtest/metrics.py`(샤프 √252·최대 낙폭·총수익률) 재사용해
      라이브 위험조정 지표 계산 (FR-006·FR-007). SC-002 는 엔진 값이 metrics 함수
      직접 호출 값과 바이트 동일함을 `test_risk_metrics_match_backtest_metrics` 로 검증.
- [X] T011 승률·평균이익/손실·손익비 청산 건당 집계 (FR-006).
- [X] T012 `--window Nd|Nh` 롤링 기간 옵션 + `--capital` 시작 자본 + 거래 0건
      시 risk=None / "거래 없음(N/A)" (US2 AC2). `--since`/`--window` 택일 검증.

P2 테스트: 단위 9건(`test_performance_risk.py`) + CLI 통합 5건. Kernel 터치 0건
(엔진은 audit_log 읽기 전용). JSON 스키마 1.0 → 1.1 (`risk` 블록 추가, 하위호환).

## P3 — 일일 리포트 통합 + 튜너 신호 면 (US5) ⏳ 대기

- [ ] T013 `auto-invest report --date`에 성과 섹션 추가 (FR-012).
- [ ] T014 (선택) `LIVE_PERFORMANCE_SNAPSHOT` 추가-전용 audit 이벤트 — K4 추가
      변경, 기본 비활성 (FR-014).

## P4 — 슬리피지/체결 품질 (US4) ⏳ 대기 (데이터 의존)

- [ ] T015 주문/시그널 시점 기준 시세 대비 체결가 슬리피지(bps·USD) 집계 (FR-009).
      **선행 의존성**: 현재 `FILL`(시장가)·`ORDER_PAPER_FILLED` 이벤트에는 "의도
      가격(기준 시세)"이 기록되지 않아 슬리피지 측정 표본이 없다. 측정 토대를 만들려면
      체결 경로에서 결정 시점 기준 시세를 추가-전용으로 한 필드 더 남겨야 한다(K4
      페이로드 소폭 확장). 그 전까지 `--slippage` 는 대부분 "측정 불가"만 나오므로,
      P2(위험조정) 완료 후 별도 데이터-캡처 변경과 함께 진행한다.

## 비고

- P1 Kernel(K1~K6, K-meta) 터치 **0건** — audit.py 는 읽기만, 수정 없음.
- spec 005(자율 튜너)는 이 하네스의 P1~P3 신호를 피드백으로 소비할 예정.
