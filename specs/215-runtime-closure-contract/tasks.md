# Tasks: 고정 실행 환경의 증거 계약
**Input**: spec.md/plan.md/research.md/data-model.md/contracts/runtime-closure.md/quickstart.md
이번 작업의 완료 대상은 설계 문서와 실제214 인계다. 후속 실행환경 구현·설치·활성화 작업은 이 목록에 포함하지 않는다.

## Setup / Foundational
- [x] T001 specs/215-runtime-closure-contract/spec.md/checklists/requirements.md에 문서 범위·위험2·검증 가능한 완료 기준을 고정한다.
- [x] T002 specs/215-runtime-closure-contract/research.md에 기존 호출부와 공식 Python/OCI 근거·대안·미관측을 조사한다.
## User Story 1
- [x] T003 [US1] specs/215-runtime-closure-contract/data-model.md/contracts/runtime-closure.md에 여섯 증거 범주·시각 연결·누락 거절을 정의한다.
- [x] T004 [US1] specs/215-runtime-closure-contract/quickstart.md에 열두 설계 반례와 예상 결과를 대응한다.
## User Story 2
- [x] T005 [US2] specs/215-runtime-closure-contract/plan.md에 배포 독립성·원래ROOT/정확HEAD·후속 등급3 구현 순서·되돌림을 고정한다.
## User Story 3
- [x] T006 [US3] specs/215-runtime-closure-contract/evidence/에 원래214 실제 예약반영/정기진단·고정5자산 검증 영수증을 보존한다.
- [x] T007 [US3] specs/214-installed-tree/tasks.md/results.md/HANDOFF.md에 기존 병합·실제반영 근거로214 T008과 지난 대기 기록을 닫는다.
## Polish / Closure
- [x] T008 specs/215-runtime-closure-contract/results.md/AGENTS.md/.specify/feature.json의 참조/문서 대응·실행파일 불변·하네스14/14·인계 사실를 확인한다. PR본문은커밋전검증후정확SHA/원격전체종료근거로갱신한다.
- [ ] T009 정확 PR HEAD의 GitHub 원래 전체XML·필수70/57/21/76/65/56/40/29무생략·린트를 확인하고 PR본문/별도 고정보관에 남긴다.
- [ ] T010 최신본문·머지가능·준비상태를 확인해 merge 병합하고 실제main을 확인한다. 단지 이 표시를 위해 문서→CI→문서 반복을 만들지 않는다.

T001→T002→T003→T004→T005→T006→T007→T008→T009→T010.
조사 역할만 읽기 전용으로 독립 검토했으며 같은 파일 편집은 순서대로 한다.
US1은 증거/반례 계약, US2는 독립배포·후속구현 계약, US3는 원래 실제 반영 자료로 각각 검토 가능하다.
최소 산출물은 US1이며 전체 인계·병합에는 세 사용자 시나리오를 모두 완료한다.
전체181 완료·실제 고정환경 인증·통과전략·연구등록·인증수집·60세션·실주문·자금의 작업 완료 표시가 아니다.
