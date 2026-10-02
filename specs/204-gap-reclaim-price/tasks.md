# Tasks: 하락 개장 후 회복 검증

## Phase 1 — Setup
- [x] T001 가설·위험·원본·경계를 spec.md와 contracts/preregistration.json에 성과 확인 전 고정한다.
- [x] T002 plan.md·research.md·data-model.md·quickstart.md와 체크리스트를 완성한다.

## Phase 2 — US1/US2 관측과 고정 입력
- [ ] T003 [US1] tests/unit/test_gap_reclaim_price_diagnostic.py에 시각·누락·변조·비용·양수 무승격 반례를 작성한다.
- [ ] T004 [US2] scripts/gap_reclaim_price_diagnostic.py에 전체 지문·정렬·시각 추출·덮어쓰기 거부를 구현한다.
- [ ] T005 [US2] research-fixtures/204에 고정 관측과 출처를 전달하고 contracts/input-lock.json 지문을 성과 확인 전 고정한다.

## Phase 3 — US3 원격 검증
- [ ] T006 [US3] score/verify와 .github/workflows/gap-reclaim-checks.yml에 원격 실제 개발·독립 산술 대조·증거 보존을 연결한다.
- [ ] T007 [US3] 원격 실제 결과·최종 전체 pytest/ruff·하네스·인계·PR 품질 검사를 results.md에 남긴다.

## Phase 4 — Release
- [ ] T008 검사 후 PR 병합·배포 감사·현장 후속 상태·전체181 미완료를 results.md와 HANDOFF.md에 인계한다.

T001→T002→T003→T004→T005→T006→T007→T008 순서다. 같은 파일 묶음이므로
이번 구현은 단일 에이전트로 진행한다. 전체181과200 T017을 대체 완료하지 않는다.
