# 작업 목록
- [x] T001 specs/220-cost-range-research/에 등급3 명세·계획·연구·계약·검증 기준을 작성한다.
- [x] T002 contracts/preregistration.json을 성과 조회 전에8befb6ce2cb243851e826fc750c8f013142df904로 커밋/푸시하고 PR899에 봉인을 기록했다. 계약0f2e08ce, 새가격재생0.
- [x] T003 [US2] tests/unit/test_cost_range_intraday.py에 인과성·문턱·누락·불완전·짧은장·1회시도 반례를 작성한다.
- [x] T004 [US2] src/auto_invest/analytics/cost_range_intraday.py 및 기존 paper의 명시적 family 연결을 구현한다.
- [x] T005 [US3] scripts/cost_range_probe.py와 tests/integration/test_cost_range_cli.py로 실제 명령/원본변조/결과위조 거절을 검증한다.
- [x] T006 [US3] .github/workflows/intraday-research-checks.yml에 비밀 없는 정확HEAD 전체검증/개발원본재생/독립재계산을 연결한다.
- [x] T007 원래 원격 XML/개발 장부/검증 자료를 읽어 지문·개별 결과를 대조하고 specs/220-cost-range-research/results.md 및 PR에 기록했다. 실제 개발 탈락과 첫 전체 회귀의 문구 호환성 1실패를 분리해 보존했고, 보정 뒤 관련74개 통과를 확인했다. 새 전체 회귀 통과는 T008에서 확인한다.
- [ ] T008 HANDOFF.md·하네스·인계 사실·PR 품질을 확인하고 전체 검증 통과 뒤 merge와 정상 배포를 확인한다.

T001→T002→T003→T004→T005→T006→T007→T008.
US1은사전등록,US2는인과적신호,US3는원본재계산으로각각검증한다.최소구현은US1+US2이며이번마감은세항목모두필요하다.
독립문서읽기만병렬가능,공유엔진편집과실제재생은직렬이다.
