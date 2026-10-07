# 작업: 장부 관측·게시 시각 연결

## Setup / foundations
- [x] T001 실제git/열린PR/209예약배포를 확인하고 별도 브랜치를 만든다.
- [x] T002 specs/210-intraday-timing/의 spec/plan/research/data-model/contracts/quickstart/점검표를 완성한다.
- [x] T003 tests/unit/test_intraday_timing.py 반례와 미구현 실패를 확인한다.

## US1
- [x] T004 [US1] src/auto_invest/analytics/intraday_timing.py의 관측·게시 시각 투영을 구현한다.
- [x] T005 [US1] scripts/intraday_timing_status.py와 deploy/observe-on-instance.sh의 같은 고정 조회를 연결한다.

## US2
- [x] T006 [US2] 같은 모듈의 잠금/DB/국소지문/불일치/비노출과209 선택적 영수증 검증을 구현한다.
- [x] T007 [US2] .github/workflows/intraday-paper-status.yml의 새반례/전체원격 검사를 연결한다.

## Closure
- [x] T008 AGENTS/.specify/209완료/HANDOFF/results/작은근거를 갱신하고 최초121개 뒤 손상메타 할당 제한 포함124개·린트·하네스14/14·인계·본문을 확인한다.
- [ ] T009 정확SHA의 실제원격XML/필수반례/린트·머지가능·최신본문 확인과 병합을 완료한다.

T001→T002→T003→T004→T005→T006→T007→T008→T009. 같은파일 동시수정 없음.
정상 예약 반영·실제원본 시각은 병합 이후 관찰 지점이며 미관측이면 명시한다.
전체181 T013~T016은 별개다.
