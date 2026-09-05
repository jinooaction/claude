# 단타 자동매매 전체 경로 작업

## Phase 1 — 기반
- [x] T001 `specs/181-intraday-runtime/`에 전체 요청과 단계별 완료 기준을 작성한다.
- [x] T002 `research.md`에서 공급자 공식 계약과 권한·시장 범위 차이를 확인한다.

## Phase 2 — US1 수집
- [x] T003 [US1] `tests/unit/test_intraday_data.py`에 페이지·오류·봉·지문 시험을 먼저 작성한다.
- [x] T004 [US1] `src/auto_invest/market_data/intraday.py`에 Alpaca/KIS 읽기 전용 수집과 내보내기를 구현한다.

## Phase 3 — US2/US3 지속 모의 운용
- [x] T005 [US2] `tests/unit/test_intraday_runtime.py`에 신호·고정 지정가·부분 체결·청산 시험을 작성한다.
- [x] T006 [US3] 같은 시험에 재시작·중복·누락·정정·동시 실행·손상 장부 시험을 추가한다.
- [x] T007 [US2] `src/auto_invest/analytics/intraday_runtime.py`에 영속 상태·주문·체결을 구현한다.
- [x] T008 [US3] `scripts/intraday_runtime.py`에 수집·재생·반복 실행·상태 명령을 연결한다.
- [x] T009 [US3] `tests/integration/test_intraday_runtime_cli.py`로 실제 CLI 실행 경로를 검증한다.

## Phase 4 — 소프트웨어 검증과 출시
- [x] T010 관련 시험·전체 pytest·ruff·strict harness·HANDOFF 사실 검사를 통과한다. 전체 3435 passed/7 skipped(761.77초), 관련48, ruff, 하네스14/14, HANDOFF OK.
- [ ] T011 `HANDOFF.md`에 구현 상태와 미완료 실운용 조건을 남기고 PR 품질 관문·merge·필요 배포를 확인한다.

## Phase 5 — US4 실제 자료와 실거래 완료 (증거 전 체크 금지)
- [ ] T012 [US4] 권한 있는 계정으로 756세션 실제 자료를 수집하고 `research.md`에 원본 지문과 완전성 증거를 남긴다.
- [ ] T013 [US4] Spec177 비용·시간 분리·다중비교 관문을 실제 자료에서 통과한 후보의 지문을 고정한다.
- [ ] T014 [US4] 동일 후보의 60세션 전진 관찰과 공급자/체결 동등성 증거를 검증한다.
- [ ] T015 [US4] 검증된 전략용 단타 반복 주문·청산 경계를 헌법·별도 등급4 명세와 함께 구현하고 강화 캐너리를 통과한다.
- [ ] T016 [US4] 소액 자동 주문·체결·청산·감사·계좌 대사·중복 방지의 생산 증거를 `HANDOFF.md`에 기록한 뒤 전체 요청 완료를 선언한다.

## 의존성과 병렬 작업

T001→T002→T003→T004, T005/T006→T007→T008/T009→T010/T011 순서다.
데이터 공식문서 조사와 로컬 구조 탐색은 독립 병렬이며 실제 소스 수정은 직렬이다.
T012는 계정 접근이 외부 조건이다. T013~T016은 시험 fixture로 대체할 수 없다.
T010/T011 완료만으로 전체 단타 구현·운영 완료를 선언하지 않는다.

2026-09-06: 코드 commit7be42cf를 PR767 초안에 올렸고 원격 품질 관문33997992037이
성공했다. T011의 기록·PR 단계는 진행했으나 merge/배포는 미완료다. 실제 자료 연결과
미구현 단타 실주문 단계를 전체 완료로 오인하지 않도록 초안 상태를 유지한다.
