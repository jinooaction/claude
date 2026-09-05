# Tasks: 첫 체결 전 자본 정합

## Phase1 Setup

- [x] T001 spec.md·plan.md·research.md·data-model.md·contracts/ladder-refresh.md에 원인·위험4·안전 계약을 고정한다.

## Phase2 US1 동일 예산 검증·실행

- [x] T002 [US1] tests/unit/test_fundability.py에142 차단/143 통과/상승가격 차단 재현.
- [x] T003 [US1] tests/unit/test_capital_ladder.py에 작은 변동·같은 금액 재실행 시험.
- [x] T004 [US1] src/auto_invest/portfolio/capital_ladder.py에 엄격한 첫 체결 전 운영1단 갱신 구현.

## Phase3 US2 실패 폐쇄

- [x] T005 [US2] tests/unit/test_capital_ladder.py에 오형식·다른예산·체결후·손실·킬스위치·NAV 반례.
- [x] T006 [US2] src/auto_invest/cli.py와 .github/workflows/forward-edge-autoarm.yml의 검증→판정→승인 경로 확인.

## Phase4 검증·출시

- [x] T007 quickstart.md의 전체검증·하네스·HANDOFF·PR 관문 및 merge·배포. PR757,
  main854d81f9, 전체3400/7, ruff·하네스14/14·HANDOFF·PR 관문 통과, deploy33928671285,
  audit33928739275 DEPLOY_COMPLETED, KIS33928671315 6/6, setup33928740976 active.
- [ ] T008 autoarm 승인 PR·merge·배포·no-order preflight 생산 결과를 quickstart.md에 기록.
- [ ] T009 실제 자동 접수·체결·감사·대사·중복차단을 확인해 specs/176-live-canary-contract/tasks.md와 HANDOFF.md 마무리.
- [x] T010 [US2] 자동 승인 checkout의 전체 이력을 선언하고 실제 Git shallow clone에서는
  인계 부모 증명이 실패하고 전체 이력에서는 통과하는 재현·회귀를 고정한다. FR-007 보정이다.
- [ ] T011 [US2] T010 전체검증·PR·배포·인계를 반영한 뒤 T008 자동 승인을 새 main에서 재실행한다.
- [x] T012 [US2] FR-008: 비-main 호스트 기본값과 색상 출력에서 동일한 승인 회귀 계약을 검사한다.
- [ ] T013 [US2] 시험 이식성 보정의 전체검증·출시·인계 후 T008 자동 승인 전체 관문을 다시 확인한다.

## Dependencies & Strategy

T001→T002/T003→T004→T005/T006→T007→T008→T009. T002와T003은 파일이 달라 독립 시험 가능하나 이번에는 순차 수행한다. US1과US2를 함께 출시하고 실제 체결은 별도 관찰한다.
