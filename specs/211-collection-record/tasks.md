# Tasks: 저장된 수집 시각의 같은 봉 연결

## Setup and Foundation
- [x] T001 실제main/열린PR/기존 구현을 확인하고 specs/211-collection-record/spec.md와 checklists/requirements.md에 범위를 고정한다.
- [x] T002 specs/211-collection-record/plan.md, research.md, data-model.md, contracts/collection-record.md, quickstart.md와 AGENTS/.specify 포인터를 연결한다.

## User Story 1 - 같은 최초 처리의 원래 시각
- [x] T003 [US1] src/auto_invest/analytics/intraday_collection_record.py에 정상/부재/손상 투영과 엄격 출력 검증을 구현한다.
- [x] T004 [US1] src/auto_invest/analytics/intraday_timing.py의 기존 읽기에 선택적 투영만 추가하고 scripts/intraday_timing_status.py의 고정 진입점을 연결한다.
- [x] T005 [US1] tests/unit/test_intraday_collection_record.py에서 원래 시각/자료 지문/최초처리/재수집/누락 합성 계약을 확인한다.

## User Story 2 - 실패 보존과 안전한 영수증
- [x] T006 [US2] src/auto_invest/analytics/intraday_diagnostic_receipt.py의 선택적 결과를 검증하고 tests/unit/test_intraday_collection_record.py의 잠금/손상/과장/출력누출/파일불변 반례를 확인한다.
- [x] T007 [US2] .github/workflows/intraday-paper-status.yml에 새 파일/필수 반례를 연결하며 기존 SSH/권한/예약을 보존한다.

## Closure
- [x] T008 HANDOFF.md/specs/211-collection-record/results.md에 실제 상태·되돌림·경계를 기록하고 린트/하네스14/14·인계e15/PR본문을 검증한다.
- [ ] T009 정확한 GitHub 전체XML/필수반례/린트/머지가능/최신본문을 확인하고 merge 방식으로 병합한다. 최종검사 근거는 PR본문과 별도 고정 보관으로 남겨 반복 문서검사를 피한다.

T001→T002→T003→T004→T005→T006→T007→T008→T009. 같은파일 동시 수정 없음.
서버 반영과 실제 원래 진단은 후속 관찰이며 미관측이면 명시한다. 전체181은 별개 미완료다.
