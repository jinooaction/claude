# 작업: 누락 보존 단타 연구 입력

## 1. 준비
- [x] T001 명세와 독립 설계 검토를 specs/193-observed-intraday-inputs/spec.md 및 research.md에 기록한다.
- [x] T002 자료/조회/CLI 계약을 specs/193-observed-intraday-inputs/data-model.md 및 contracts/cli.md에 고정한다.

## 2. 공통 기반
- [ ] T003 src/auto_invest/analytics/observed_intraday_inputs.py에 원본 지문/manifest/1분 CSV 유효성 검증과 불변 타입을 구현한다.

## 3. US1 전체 달력과 누락
독립 검사: 전체 결측일/종목, 휴일/DST/조기폐장과 불완전 봉을 대조한다.
- [ ] T004 [US1] tests/unit/test_observed_intraday_inputs.py에 격자/중복/비정상값/누락 반례를 추가한다.
- [ ] T005 [US1] src/auto_invest/analytics/observed_intraday_inputs.py에 고정 달력 및 완성 창/누락 마스크를 구현한다.

## 4. US2 당시 입력만 조회
독립 검사: 미래 행 변조 후 지문이 아닌 과거 판정/사용 관측의 불변성을 확인한다.
- [ ] T006 [US2] tests/unit/test_observed_intraday_inputs.py에 오후 삭제/미완결 창/과거14일 누락 반례를 추가한다.
- [ ] T007 [US2] src/auto_invest/analytics/observed_intraday_inputs.py에 as_of와 요청 창별 적격성 조회를 구현한다.

## 5. US3 체결 관측 구분
독립 검사: 해당 분봉 시가와 분 종료 후 거래량, 미관측 진입과 청산을 구분한다.
- [ ] T008 [US3] tests/unit/test_observed_intraday_inputs.py에0거래량/다음날만 관측/끝까지 관측 없음 반례를 추가한다.
- [ ] T009 [US3] src/auto_invest/analytics/observed_intraday_inputs.py에 정확 시각/이후 최초 관측 조회와 미해결 반환을 구현한다.

## 6. 통합과 실제 자료
- [ ] T010 scripts/observed_intraday_probe.py 및 tests/integration/test_observed_intraday_cli.py에 읽기 전용 감사 CLI/지문/덮어쓰기 거부를 구현·검증한다.
- [ ] T011 실제 RTX/DD 감사 대조와 미확인 식별 상태를 specs/193-observed-intraday-inputs/results.md에 기록한다.
- [ ] T012 전체pytest/ruff·기존192 회귀·하네스/인계 결과를 specs/193-observed-intraday-inputs/results.md에 기록한다.
- [ ] T013 PR 준비/머지와 실제 배포 해당 여부를 확인하고 HANDOFF.md를 갱신한다.

의존 순서: T001~T003→US1→US2/US3→통합→실자료→전체검증→출시.
단일 구현 파일을 공유하므로 구현은 직렬화한다. 각 이야기의 읽기 전용 반례 검토는
별도 작업으로 병렬 가능하지만, 같은 테스트 파일을 동시에 수정하지 않는다.
첫 증분은 US1이며 전체193완료는 US2/US3와 통합까지 필요하다.
193완료는181전략 통과/전진관찰/실운영 증거를 대체하지 않는다.
