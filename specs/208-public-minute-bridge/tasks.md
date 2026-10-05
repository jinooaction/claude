# Tasks: 보관 분봉 운영 연결

## Phase 1: Setup / foundations

- [x] T001 최신main/열린PR/작업충돌 확인, 별도208 브랜치, 명세/품질 검사.
- [x] T002 설계·판단·자료·실행 계약과 포인터를 검토한다.
- [x] T003 `tests/unit/test_public_minute_bridge.py`/`tests/integration/test_public_minute_bridge_cli.py`에 의미 있는 반례를 먼저 쓰고 실패를 확인한다. 모듈/스크립트 부재 실패 확인 뒤 실제 AEAD 합성 복원까지40개 무생략 통과.

## Phase 2: User Story 1

- [x] T004 [US1] `scripts/public_minute_bridge.py`의 고정6자산/원격SHA/원본 인증·안전 실패 영수증을 구현한다.
- [x] T005 [US1] `.github/workflows/public-minute-bridge.yml`의 정확SHA/영구선점/키 경계를 구현한다. 실제 최초 원격 실행은T011에서 확인한다.

## Phase 3: User Story 2

- [x] T006 [US2] `market_data/public_minute_bridge.py`의 실제 달력·분누락·5분 집계·정규화·모형 시각을 구현한다.
- [x] T007 [US2] 모든 날짜×5종목과 실제 공통 날짜 교집합/원래 분누락 대조를 구현한다.

## Phase 4: User Story 3 / closure

- [x] T008 [US3] 모든 성공/실패의 자격 거짓·가격 비노출·성과 미조회·한도 보존을 검사한다.
- [x] T009 작은 합성 검사40개 무생략(1.58초)/린트/워크플로 구문·고정6원격지문/하네스14·14/인계 사실을 확인한다. PR 본문은 생성 전에 별도 검사한다.
- [x] T010 정확검토c64a9ddc의37339143058/37339143232는각5358 passed/13 skipped/실패0·XML1474.687/1310.628초·신규40개/기존명령29개무생략·린트 성공. 실제XML/원래ZIP크기·SHA대조.
- [x] T011 실제고정6자산/두전체원본AEAD/평문SHA와210상태/원래분누락·분완전날짜/실제5종목교집합3일을대조했다. 새release403924138의정확3자산101432바이트/원격SHA대조,성과조회/주문0/자격거짓보존.
- [ ] T012 결과/인계를 남기고 최종 검증 뒤 병합한다.

T001→T002→T003→T004/T006/T007/T008→T005→T009→T010→T011→T012.
동일 파일 병렬 수정 없음. 실제 검증 전 T010~T012를 완료 표시하지 않는다.
