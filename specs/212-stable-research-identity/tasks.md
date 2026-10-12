# Tasks: 재검증 시각과 연구 내용 지문 분리

## Setup
- [x] T001 specs/212-stable-research-identity/spec.md와 checklists/requirements.md에 재현·위험등급3·안전 경계를 고정한다.
- [x] T002 specs/212-stable-research-identity/plan.md, research.md, data-model.md, contracts/research-identity.md, quickstart.md와 AGENTS/.specify 포인터를 연결한다.

## User Story 1 - 같은 연구 재현
- [x] T003 [US1] tests/unit/test_intraday_research_identity.py에 다른 재검증시각/같은 원본·코드·내용 지문과 원래생성시각·원본불변 반례를 작성하고 보정 전3실패/10통과·1.64초를 확인한다.
- [x] T004 [US1] src/auto_invest/analytics/intraday_research_identity.py와 intraday_archive.py에 원래 archive 입력 지문을 연결한다.
- [x] T005 [US1] src/auto_invest/execution/intraday_selection.py에서 새 버전의 전체 연구 내용 지문을 계산하고 intraday_identity.py의 실행 지문에도 새 모듈을 추가한다.

## User Story 2 - 내용 변경/이전등록 거절
- [x] T006 [US2] tests/unit/test_intraday_research_identity.py에서 원본·시각·출처·조정·판정·후보·비용·코드·알 수 없는 필드 변경과 등록 연결/이전 지문 거절을 확인한다.
- [x] T007 [US2] .github/workflows/stable-research-identity-checks.yml에 broker 비밀·가격재생 없는 전체XML/필수반례/린트 보관을 연결한다.

## Closure
- [x] T008 specs/212-stable-research-identity/results.md와 HANDOFF.md에 실제 보정/합성·미관측범위/되돌림을 기록하고 하네스14/14·인계·본문을 확인한다.
- [x] T009 정확 GitHub 전체XML/필수반례/린트/본문/머지가능을 확인하고 merge 병합한다. PR886/main e05a7ad3·38067627942 실제5577통과/13건너뜀/실패0/1400.281초·신규21/76/65/56/40/29무생략·린트, 고정release409076859 근거로213의 정당한 후속 기록에서 닫았다.
- [x] T010 정상 배포의 실제serverHEAD/감사·읽기 전용 원래진단의 범위를 확인한다. 감사38069543758/시작19960·완료19965·2026-10-10 16:53:24.718UTC main e05a7ad3 반영과 원래진단38069545705/고정release409079356으로 확인했다. 실제전략/등록/체결은 따로 미평가다. 재배포·진단 재실행 없음.

T001→T002→T003→T004→T005→T006→T007→T008→T009→T010.
구현파일은 순서대로 수정한다. 독립 문서 검토만 병렬 가능하며 같은 파일/브랜치 병렬수정은 없다.
