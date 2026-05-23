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

## P2 — 위험조정 성과 (US2) ⏳ 대기

- [ ] T009 일별 손익/자산 시계열을 audit_log 체결에서 재구성.
- [ ] T010 spec 008 `backtest/metrics.py`(샤프 √252·최대 낙폭·수익률) 재사용해
      라이브 위험조정 지표 계산 (FR-006·FR-007, SC-002 백테스트와 수치 일치).
- [ ] T011 승률·평균이익/손실·손익비 (FR-006).
- [ ] T012 `--window 30d` 등 롤링 기간 옵션 + 거래 0건 N/A (US2 AC2).

## P3 — 일일 리포트 통합 + 튜너 신호 면 (US5) ⏳ 대기

- [ ] T013 `auto-invest report --date`에 성과 섹션 추가 (FR-012).
- [ ] T014 (선택) `LIVE_PERFORMANCE_SNAPSHOT` 추가-전용 audit 이벤트 — K4 추가
      변경, 기본 비활성 (FR-014).

## P4 — 슬리피지/체결 품질 (US4) ⏳ 대기

- [ ] T015 주문/시그널 시점 기준 시세 대비 체결가 슬리피지(bps·USD) 집계 (FR-009).

## 비고

- P1 Kernel(K1~K6, K-meta) 터치 **0건** — audit.py 는 읽기만, 수정 없음.
- spec 005(자율 튜너)는 이 하네스의 P1~P3 신호를 피드백으로 소비할 예정.
