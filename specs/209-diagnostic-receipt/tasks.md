# 작업: 진단 원본 영수증

## Setup / foundations
- [x] T001 실제git/PR/배포·제한/원격관측을확인하고209별도브랜치를만든다.
- [x] T002 이폴더spec/plan/research/data-model/contracts/quickstart/점검표를완성한다.
- [x] T003 tests/unit/test_intraday_diagnostic_receipt.py에의미있는반례를만들어미구현실패를확인한다.

## US1 — 원래값 보관
- [x] T004 [US1] src/auto_invest/analytics/intraday_diagnostic_receipt.py의원본/타입/시각/지문검증을구현한다.

## US2 — 범위/비노출
- [x] T005 [US2] 같은모듈의허용필드/자격거짓/노출·덮어쓰기안전실패와CLI를구현한다.

## US3 — 원격 적용
- [x] T006 [US3] .github/workflows/intraday-paper-status.yml에키없는전체PR검사와기존관측JSON artifact보관을연결한다.

## Closure
- [x] T007 AGENTS/.specify·208완료/HANDOFF·results·작은증거를남기고합성56개/린트/하네스14·14/인계/본문을검증한다. 실제 shell의 SSH 오류를 tee가 덮는 실패도 재현·보정했다.
- [ ] T008 실제원격전체XML/필수반례/린트와같은검토코드의관측artifact를대조하고본문·병합을완료한다.

T001→T002→T003→T004→T005→T006→T007→T008. 같은파일병렬수정없음.
전체181 T013~T016은이진단영수증의완료로대체되지않는다.
