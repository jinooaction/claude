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

- [ ] T007 quickstart.md의 전체검증·하네스·HANDOFF·PR 관문 및 merge·배포.
- [ ] T008 autoarm 승인 PR·merge·배포·no-order preflight 생산 결과를 quickstart.md에 기록.
- [ ] T009 실제 자동 접수·체결·감사·대사·중복차단을 확인해 specs/176-live-canary-contract/tasks.md와 HANDOFF.md 마무리.

## Dependencies & Strategy

T001→T002/T003→T004→T005/T006→T007→T008→T009. T002와T003은 파일이 달라 독립 시험 가능하나 이번에는 순차 수행한다. US1과US2를 함께 출시하고 실제 체결은 별도 관찰한다.
