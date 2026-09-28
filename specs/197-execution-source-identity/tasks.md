# Tasks: 실행 검증의 코드 연결 보완

## Phase 1 — 설계
- [x] T001 specs/197-execution-source-identity/ 명세·계획·조사·자료·계약·검사표 작성.
- [x] T002 .specify/feature.json 및 AGENTS.md 포인터 연결과 선행 경로 검사.
## Phase 2 — US1 변경 검출
- [x] T003 tests/unit/test_intraday_identity.py에서 네 누락 소스 변경의 실패를 먼저 재현.
- [x] T004 src/auto_invest/execution/intraday_identity.py 소스 목록·읽기를 구현하고 intraday_signals.py에 연결.
- [x] T005 tests/unit/test_intraday_identity.py의 정적 의존 누락·경로/내용 재현성·기존 소스 보존 검증.
## Phase 3 — US2 실패와 호환성
- [x] T006 tests/unit/test_intraday_identity.py의 누락·중복·링크·읽기 실패·검사 중 변경·문서 비영향 검사.
- [x] T007 tests/unit/test_intraday_qualification.py의 과거 지문 자격 거부·기존 등록 검사와 실제 자체 시험 확인.
## Phase 4 — 출시
- [ ] T008 specs/197-execution-source-identity/results.md에 계산 비용·관련/전체 회귀·린트·하네스·인계 결과 기록.
- [ ] T009 품질 관문 PR 병합·배포 확인 후 HANDOFF.md와 results.md 갱신. 전체181 조건 유지.

T001→T002→T003→T004→T005/T006→T007→T008→T009. 단일 작업자가 수행하며 추가 에이전트는 필요하지 않다.
