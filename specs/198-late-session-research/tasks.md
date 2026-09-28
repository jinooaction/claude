# 작업표: 장 마감 전 단일 후보 검증

## Phase 1 — 명세와 사전등록

- [x] T001 명세·설계·자료 구조·계약 작성: `specs/198-late-session-research/`.
- [x] T002 성과 확인 전 계약 검증·커밋·초안 PR 보존: `contracts/preregistration.json`. 사전등록 f77301e, 초안 PR #857, 가격 미조회.

## Phase 2 — 공통 기반

- [ ] T003 고정 계약·manifest 검사와 후보 정체성 구현: `src/auto_invest/analytics/late_session_intraday.py`.

## Phase 3 — US1 시각이 정확한 단일 신호

독립 검사: 정상장·반일장·휴일·동일가·입력 누락·미래 변경 반례로 신호를 확인한다.

- [ ] T004 [US1] 시간·전일·누락·미래 불변 시험: `tests/unit/test_late_session_intraday.py`.
- [ ] T005 [US1] 직전 종가·두 관측 시점의 신호 계산: `src/auto_invest/analytics/late_session_intraday.py`.
- [ ] T006 [US1] 별도 계열·매핑 범위·매수 시도 제한 연결과 기존 계열 회귀: `src/auto_invest/analytics/intraday_paper_challenger.py`.

## Phase 4 — US2 비용과 미체결 판정

독립 검사: 미체결 매수·부분 청산·마지막 봉 유동성 부족을 장부와 판정에서 확인한다.

- [ ] T007 [US2] 두 비용·시도·청산 잔여 수량 시험: `tests/unit/test_late_session_intraday.py`.
- [ ] T008 [US2] 준비 1일·평가 1,644일·기존 통과 기준·한계 보고 구현: `src/auto_invest/analytics/late_session_intraday.py`.

## Phase 5 — US3 원자료로 재현

독립 검사: 자료·계약·장부·판정 변조, 잘못된 입력·출력 거부와 원자료 재계산.

- [ ] T009 [US3] 명령·변조·최종 확인 미접근 시험: `tests/integration/test_late_session_cli.py`.
- [ ] T010 [US3] develop/verify·깨끗한 코드·새 출력·재계산 구현: `scripts/late_session_probe.py`.

## Phase 6 — 실제 검증과 인계

- [ ] T011 원격 실행 위치·자료 전송 범위 확인 및 실제 개발/재계산: `specs/198-late-session-research/results.md`.
- [ ] T012 원격 전체 pytest·ruff, 하네스·HANDOFF·PR 품질 검사 기록: `specs/198-late-session-research/results.md`.
- [ ] T013 PR 병합·필요한 배포 검증·현재 상태 인계: `HANDOFF.md`.

## 의존성과 구현 순서

T001→T002→T003→T004/T005→T006→T007/T008→T009/T010→T011→T012→T013.
US1 신호가 첫 검증 단위이며 US2·US3까지 진행해야 기능이 완성된다.
각 이야기의 시험 작성과 문서 검토는 다른 파일에서 병렬 가능하지만, 이번 작업은
Mac 자원 사용을 줄이기 위해 직렬 실행한다. 공유 체결 엔진 수정은 반드시 직렬이다.
무거운 검증을 로컬에서 실행하지 않는다. 계약 고정 전 성과 계산을 하지 않는다.

이 작업표 완료는 전체 목표 완료가 아니다. 181 T013~T016과 197 배포의 현재 증거를
별도로 확인하며 연구 결과가 탈락이면 해당 후보를 보존하고 다음 대안을 찾는다.
