# Tasks: 후보 고정 환경 사전 확인

## Setup
- [x] T001 specs/213-frozen-context/spec.md와 checklists/requirements.md에 범위·제한·안전 경계를 고정한다.
- [x] T002 specs/213-frozen-context/plan.md/research.md/data-model.md/contracts/context.md/quickstart.md와 AGENTS/.specify 포인터를 연결한다.

## User Story 1
- [x] T003 [US1] tests/unit/test_intraday_frozen_context.py에 독립 합성 저장소/선언·모듈·환경 비교를 작성한다.
- [x] T004 [US1] scripts/intraday_frozen_context.py에 제한된 읽기·기대 환경 검증·Git/lock/현재 실행기 비교를 구현한다.

## User Story 2
- [x] T005 [US2] tests/unit/test_intraday_frozen_context.py에 경로·dirty·같은트리다른HEAD·의존성·모듈·동시변경·실패·비실행 반례를 완성한다.
- [x] T006 [US2] .github/workflows/frozen-context-checks.yml에 비밀·가격 없는 정확 전체XML·필수반례·린트를 연결한다.

## Closure
- [x] T007 specs/213-frozen-context/results.md/HANDOFF.md에 실제 범위·미평가·되돌림을 기록하고 하네스14/14·main e05 인계 사실·본문을 확인한다. 212 완료 표시는 기존 고정 근거로 닫는다.
- [x] T008 정확 GitHub 전체XML/필수반례/린트/본문/머지가능을 확인해 merge 병합하고 실제main을 확인한다. PR887/main19e77b6b·38274702004/38274701812의 실제XML5634통과/13건너뜀/실패0와 고정release410810510을 대조했다. 예약배포19985→19990/2026-10-12 21:00:15.156UTC 실제완료·원래정기진단38337850148도 별도 검증했다.

T001→T002→T003→T004→T005→T006→T007→T008. 같은 파일/브랜치 병렬 수정 없음.
다른 문서 검토만 독립 가능. 이번 완료 기준에 실제 환경 설치/등록/수집 활성화는 포함되지 않는다.
