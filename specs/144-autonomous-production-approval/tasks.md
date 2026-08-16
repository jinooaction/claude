# Tasks: Autonomous Production Approval

## Phase 1: Setup

- [x] T001 위험 4등급 문제 정의와 안전 경계를 `specs/144-autonomous-production-approval/`에 기록한다.

## Phase 2: User Story 1 - 사람 없는 예약 주문 승인

- [x] T002 [US1] `.github/workflows/rebalance-live-canary.yml`에 독립 기계 승인 작업과 명시적 이벤트 분기를 추가한다.
- [x] T003 [US1] `tests/unit/test_live_canary_workflow.py`에 main·이벤트·기계 승인 의존성과 수동 주문 0건 회귀를 추가한다.

## Phase 3: User Story 2 - 정직한 상태 표시

- [x] T004 [US2] `src/auto_invest/analytics/money_path.py`의 사람 승인 문구를 production 기계 승인으로 바꾼다.
- [x] T005 [US2] `tests/unit/test_money_path.py`에 새 필수 관문 문구를 검증한다.

## Phase 4: Verification And Release

- [x] T006 관련·전체 테스트, ruff, 셸·YAML·diff, 엄격 하네스, HANDOFF 사실 검사를 통과한다.
- [x] T007 안전 경계 커밋·PR·자동 머지와 배포 성공을 확인한다.
- [x] T008 GitHub production required reviewer를 0명으로 만들고 main-only 정책을 재확인한다.
- [ ] T009 주문 없는 수동 production 사전점검이 사람 대기 없이 성공하는지 확인한다.
- [ ] T010 money-path와 capital readiness를 재발행해 자동매매 상태를 확인하고 HANDOFF를 갱신한다.
- [x] T011 첫 실서버 사전점검에서 발견한 기계 승인 checkout 누락을 고치고 회귀 테스트를 추가한다.

## Dependencies

- T002-T005가 T006을 선행한다.
- T006이 T007을, T007이 T008-T010을 선행한다.
- T009는 실제 주문 없이 서명·서버 권위·사람 없는 production 진입을 독립 검증한다.
