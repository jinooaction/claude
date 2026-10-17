# 작업 순서
- [x] T001 specs/219-source-input-lab/spec.md·plan.md·research.md에 범위와 판단을 고정한다.
- [x] T002 [US1] tests/unit/test_intraday_source_input_lab.py에 입력·환경·한도 반례를 작성한다.
- [x] T003 [US1] scripts/intraday_source_input_lab.py에 원래 파일과 실제 Git 검사·변조 lab을 구현한다.
- [x] T004 [US2] scripts/intraday_source_input_lab.py에 독립 toy 설치 입력·선언 비교를 구현한다.
- [x] T005 [US3] .github/workflows/source-input-lab.yml에 비밀 없는 원격 lab/전체 회귀 및 무생략 검사를 연결한다.
- [x] T006 [US3] HANDOFF.md와 specs/219-source-input-lab/results.md에 실제 배포와 새 구현의 한도·증거를 기록한다.
- [ ] T007 정확 PR HEAD의 원격 전체 검증과 원래 artifact를 확인하고 PR 본문에 기록한다.
- [ ] T008 merge/main·정상 배포 상태를 확인하고 다음 실행 조건을 인계한다.

T001→T002→T003→T004→T005→T006→T007→T008. 독립 읽기만 병렬 가능하며 파일 변경은 직렬.
최소 가치는 US1의 입력 변조 거절이며 이번 병합은 US1~3 모두 필요하다.
