# Tasks: 공식 거시 발표일 가격 진단

## Phase 1 — Setup

- [x] T001 원본 지문과 단일 가설·비용·기간을 `specs/203-macro-release-price/contracts/preregistration.json`에 결과 조회 전에 커밋한다.

## Phase 2 — Foundational

- [x] T002 고정 발표 원본의 가족·공식 날짜·시각·휴장·중복 감사와 입력 변조 거부를 `scripts/macro_release_price_diagnostic.py`에 구현한다.

## Phase 3 — User Story 1: 발표 원본

- [x] T003 [US1] 잘못된 취소 상태·비공식 날짜·재수정일·휴장·일광절약시간 반례를 `tests/unit/test_macro_release_price_diagnostic.py`에 추가한다.

## Phase 4 — User Story 2: 개발 가격 진단

- [x] T004 [US2] 정확한 전일 종가·09:45 신호·09:55/15:55 가격·거래량·비용 계산을 `scripts/macro_release_price_diagnostic.py`에 구현한다.
- [x] T005 [US2] 누락·중복·미래 구간·지문 변조·비용 계산 반례를 `tests/unit/test_macro_release_price_diagnostic.py`에 추가한다.

## Phase 5 — User Story 3: 연구 판정

- [x] T006 [US3] 실제 개발 구간을 저장소 밖 출력으로 한 번 재생하고 `specs/203-macro-release-price/results.md`에 지문·결과·미완료 관문을 남긴다.

## Phase 6 — 검증과 인계

- [ ] T007 전체 원격 회귀·린트·하네스·인계 사실·PR 품질 검사를 통과하고 `specs/203-macro-release-price/results.md`에 기록한다.
- [ ] T008 병합·배포 해당 여부를 확인하고 Spec 181 T013~T016을 `HANDOFF.md`에 정확히 인계한다.

의존성: T001→T002/T003→T004/T005→T006→T007→T008.
2018년 이후의 수익은 개발 가설 탈락 시 열지 않는다.
