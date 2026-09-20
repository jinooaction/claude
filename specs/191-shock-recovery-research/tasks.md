# 작업표

## Phase 1 — 사전등록
- [x] T001 명세·계획·계약을 작성한다: `specs/191-shock-recovery-research/`.
- [x] T002 성과를 읽기 전에 계약을 커밋하고 지문을 고정한다: `specs/191-shock-recovery-research/contracts/preregistration.json`. 사전등록 fdaa14b, SHA256 6665cab7eb7fb87b6ee11258f8323455087b00471036ed149006948961af9761.

## Phase 2 — US1 신호
- [x] T003 [US1]4후보·신호·하루1시도를 구현한다: `src/auto_invest/analytics/shock_recovery_intraday.py`, `intraday_paper_challenger.py`.
- [x] T004 [US1] 미래불변·임계값·미체결·갭·재진입·청산 반례를 검증한다: `tests/unit/test_shock_recovery_intraday.py`.

## Phase 3 — US2 개발 실행
- [x] T005 [US2] 입력 고정·두 비용 재생·탈락/확인 필요 판정을 구현한다: `src/auto_invest/analytics/shock_recovery_intraday.py`.
- [x] T006 [US2] 커밋된 코드와 새 출력만 받는 명령을 구현한다: `scripts/shock_recovery_probe.py`.

## Phase 4 — US3 재현 검사
- [x] T007 [US3] 해시·코드 계보·원본 재계산을 구현한다: `scripts/shock_recovery_probe.py`, `src/auto_invest/analytics/shock_recovery_intraday.py`.
- [x] T008 [US3] 변조·잘못된 입력·덮어쓰기·확인 명령 부재를 검사한다: `tests/integration/test_shock_recovery_cli.py`.

## Phase 5 — 실제 결과와 출시
- [x] T009 커밋 후 실제1645일 재생/재계산을 완료한다: `specs/191-shock-recovery-research/results.md`. 수정91a2b55, 재계산83436 exit0,4208행 일치,4후보 모두 탈락.
- [ ] T010 전체 pytest/ruff·하네스·HANDOFF·PR 품질을 검증한다: `specs/191-shock-recovery-research/results.md`.
- [ ] T011 PR 병합·필요한 배포 확인·인계를 완료한다: `HANDOFF.md`.

## 의존성과 검증 단위

T001→T002→T003/T004→T005/T006→T007/T008→T009→T010→T011.
US1은 신호/장부 반례, US2는 개발 재생, US3는 변조 거부와 재현으로 독립 확인한다.
병렬 가능 예: 읽기 전용 신호 설계 검토와 명세 작성. 공유 파일 구현은 순서대로 한다.
확인495일을 여는 추가 단계는 이번 개발 기능에 없으며 전체 목표에서는 계속 남는다.
