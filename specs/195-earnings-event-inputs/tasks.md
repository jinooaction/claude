# Tasks: 관측 시점이 보존되는 실적 사건 입력

## Phase 1: Setup
- [x] T001 명세·계획·연구 판단을 specs/195-earnings-event-inputs/에 작성하고 .specify/feature.json 및 AGENTS.md 포인터 연결.

## Phase 2: Foundational
- [x] T002 입력과 조회 경계를 specs/195-earnings-event-inputs/data-model.md 및 contracts/cli.md에 고정.
- [x] T003 tests/unit/test_earnings_event_inputs.py에 원문·시각·버전 반례 작성 후 실패 확인.

## Phase 3: US1 원문과 사건
독립 검사: 로컬 원문 등록 성공, 변조·잘못된 인용·중복·잘못된 식별자는 거부.
- [x] T004 [US1] src/auto_invest/analytics/earnings_event_inputs.py에 엄격 입력과 원문 스냅샷 구현.

## Phase 4: US2 기준 시점 조회
독립 검사: 현재 옛 문서의 과거 노출 0건, 정정본 추가 전후 과거 조회 불변.
- [x] T005 [US2] src/auto_invest/analytics/earnings_event_inputs.py에 버전 연결과 기준 시점 조회 구현.
- [x] T006 [US2] tests/integration/test_earnings_event_inputs_cli.py 실패 확인 후 scripts/earnings_event_inputs.py에 import/query 연결.

## Phase 5: 실제 자료와 완료 검사
- [x] T007 실제 보존 원문 2개로 import/query 실행 후 specs/195-earnings-event-inputs/results.md에 기록.
- [x] T008 전체 회귀·린트·하네스·인계 검사 결과를 specs/195-earnings-event-inputs/results.md에 기록하고 PR 검증.
- [ ] T009 병합·필요 배포 증거와 다음 작업을 HANDOFF.md 및 specs/195-earnings-event-inputs/results.md에 인계.

## Dependencies and execution
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009.
순차 구현한다. 독립 파일인 원문 반례와 CLI 반례는 병렬 검토 가능하지만 같은 코드는 동시 편집하지 않는다.
US1 먼저 검사 후 US2를 연결한다. 후속 전체 역사 확보·전진 수집·전략 검증은 전체 목표의 남은 작업이다.
