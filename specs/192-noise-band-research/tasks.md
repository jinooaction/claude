# 작업표
## Phase 1 — 사전등록
- [x] T001 명세/원문/설계/계약 작성: `specs/192-noise-band-research/`.
- [x] T002 성과 확인 전 계약 커밋: `contracts/preregistration.json`.
## Phase 2 — US1 인과적 신호
- [x] T003 [US1]14일/갭/시간/누락/경계 시험: `tests/unit/test_noise_band_intraday.py`.
- [x] T004 [US1] 슬롯별 신호 계산: `src/auto_invest/analytics/noise_band_intraday.py`.
- [x] T005 [US1] 매핑/시도/청산 연결·기존 회귀: `src/auto_invest/analytics/intraday_paper_challenger.py`.
## Phase 3 — US2/US3 개발과 재현
- [x] T006 [US2] 고정입력·두비용·1631일 지표: `src/auto_invest/analytics/noise_band_intraday.py`.
- [x] T007 [US3] 지문/재계산/덮어쓰기 거부: `scripts/noise_band_probe.py`.
- [x] T008 [US3] 명령/변조/holdout미접근 시험: `tests/integration/test_noise_band_cli.py`.
## Phase 4 — 실제 검증과 출시
- [x] T009 실제 개발/재계산 결과: `results.md`. dfced27,21316/51925 exit0,10160장부행 일치, 단일 후보 양비용 탈락.
- [x] T010 전체 pytest/ruff·하네스/HANDOFF/PR검증: `results.md`. dfced27,4841 passed/13 skipped,9308 exit0,ruff·하네스14/14·HANDOFF·PR품질 통과.
- [ ] T011 PR병합·배포·인계: `HANDOFF.md`.

T001→T002→T003/T004→T005→T006/T007/T008→T009→T010→T011.
독립 시험은 신호,판정,재현 경계로 나눈다. 읽기 전용 설계검토만 병렬 수행했다.
공유 엔진 수정은 직렬이며 기존28실패와 전체 목표 미완료를 유지한다.
