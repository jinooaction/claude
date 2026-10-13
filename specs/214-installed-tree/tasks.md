# Tasks: 설치 폴더 비교
## Setup
- [x] T001 specs/214-installed-tree/spec.md/checklists/requirements.md에 범위·위험2·완료 기준을 고정한다.
- [x] T002 specs/214-installed-tree/plan.md/research.md/data-model.md/contracts/compare.md/quickstart.md와 AGENTS/.specify를 연결한다.
## User Story 1
- [x] T003 [US1] tests/unit/test_intraday_installed_tree.py에 같은 버전 변조/추가/삭제/권한·빈 폴더 반례를 작성한다.
- [x] T004 [US1] scripts/intraday_installed_tree.py에 폐쇄형 선언·fd 조회/지문/두 관측 비교를 구현한다.
## User Story 2
- [x] T005 [US2] tests/unit/test_intraday_installed_tree.py에 링크/특수파일/별칭/동시변경/한도/비실행·비공개 반례를 완성한다.
- [x] T006 [US2] .github/workflows/installed-tree-checks.yml에 정확 HEAD 전체XML/무생략·린트를 연결한다.
## Closure
- [x] T007 specs/214-installed-tree/results.md/HANDOFF.md에 실제 결과/213 완료근거·미평가·되돌림을 기록하고 하네스/인계/본문을 확인한다.
- [ ] T008 정확 원격XML/무생략·린트·본문/머지가능을 확인해 merge 병합하고 실제main을 확인한다. 근거는PR/별도보관으로 남긴다.
T001→T002→T003→T004→T005→T006→T007→T008。문서별 검토는 독립 가능하며 이 세션은 순서대로 진행한다.
실제 설치/활성화·전체 실행환경 인증/등록/수집·60세션·실주문은 이번 완료 범위 밖이다.
