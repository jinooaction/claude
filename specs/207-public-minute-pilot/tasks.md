# Tasks: 공개 분봉 원본 검증

## Phase 1: Setup

- [x] T001 최신 main/열린 PR/작업 충돌을 확인하고 별도207 브랜치를 만든다.
- [x] T002 `spec.md`/`checklists/requirements.md`의 사용자 흐름·범위·완료 기준을 검토한다.
- [x] T003 `plan.md`/`research.md`/`data-model.md`/`contracts/pilot.md`/`quickstart.md`와 에이전트 포인터를 준비한다.

## Phase 2: Foundational

- [x] T004 `tests/unit/test_public_minute.py`와 `tests/integration/test_public_minute_pilot.py`에 요청/지문/시간/품질/비노출/암호화 반례를 먼저 쓰고 실패를 확인한다. 구현 전 모듈 부재 실패 확인, 이후 합성40개 무생략 통과.

## Phase 3: User Story 1

- [x] T005 [US1] `src/auto_invest/market_data/public_minute.py`에 고정 익명 원본·제한 스트리밍·주소/재시도/시간 관문을 구현한다.
- [x] T006 [US1] `scripts/public_minute_pilot.py`에 부분 실패를 확보 성공으로 표시하지 않는 안전 영수증을 구현한다.

## Phase 4: User Story 2

- [x] T007 [US2] `public_minute.py`에 뉴욕 월/실제 달력/봉 가용 시각·가격·거래량·중복·종목별 정규장 완전성 보고를 구현한다.
- [x] T008 [US2] 미확인 출처·제공자/전략 자격 거짓·미개봉/수익률 미조회 계약을 검사한다.

## Phase 5: User Story 3

- [x] T009 [US3] `public_minute_pilot.py`에 원본별 AES-GCM 암호화·지문/부가 인증 문맥·추가 전용 출력 및 재검증을 구현한다.
- [x] T010 [US3] `.github/workflows/public-minute-pilot.yml`에 정확 검토 코드 관문·영구 선점·첫 실패 후 반복 차단·안전 결과/암호문 보관을 연결한다. 실제 원격 최초 실행/재실행 관측은 T012에서 확인한다.

## Phase 6: Polish / actual closure

- [x] T011 작은 합성 검사·린트·명세 경로·엄격 하네스·HANDOFF 사실·PR 본문 품질을 확인한다. 합성40개·린트·하네스14/14·실제main9d70758c/5278·13 인계 사실 확인. 원격 전체 검사는 별도 T012다.
- [ ] T012 검토 SHA의 실제 원격 전체 회귀와 고정 두 전체 원본 지문·품질·암호화/영구 자산 지문을 확인한다.
- [ ] T013 `HANDOFF.md`/실제 결과/PR에 소프트웨어·취득·품질·전체181 미완료를 구분해 남기고 검증 후 병합한다.

## Dependencies / execution

T001~T003→T004→T005/T006→T007/T008→T009→T010→T011→T012→T013.
동일 파일을 나누어 병렬 수정하지 않는다. 실제 원격 취득 전까지 T012를 완료하지 않는다.
신규 전략 가설/성과는 없고 최소36시도·미개봉495세션을 유지한다. 실제 주문/자본0.
