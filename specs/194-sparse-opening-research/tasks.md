# Tasks: 누락 보존 시초 돌파 연구

## 준비
- [x] T001 specs/194-sparse-opening-research/spec.md와 research.md에 요구·독립 검토를 기록한다.
- [x] T002 specs/194-sparse-opening-research/contracts/preregistration.json의 경계 사례와30개 원본 지문 연결을 검토하고 성과 조회 전 봉인한다.

## 기반
- [ ] T003 src/auto_invest/analytics/sparse_opening_research.py에 계약/manifest 검증과 날짜별 관측 입력을 구현한다.

## US1 당시 신호
독립 검사:미래 행 변경·정확14일 누락·09:40/10:30경계를 확인한다.
- [ ] T004 [US1] tests/unit/test_sparse_opening_research.py에 신호와 시도권 반례를 작성한다.
- [ ] T005 [US1] src/auto_invest/analytics/sparse_opening_research.py에 단일 후보의 시초 창·돌파·청산 의도를 구현한다.

## US2 현금과 잔량
독립 검사:동시 현금 경합·부분 참조·익일 청산·결제 지연·자본 소진을 대조한다.
- [ ] T006 [US2] tests/unit/test_sparse_opening_research.py에 현금 예약/결제/잔량 반례를 작성한다.
- [ ] T007 [US2] src/auto_invest/analytics/sparse_opening_research.py에 기간 전체 시간순 계좌와 연구 장부를 구현한다.

## US3 재현 결과
독립 검사:실제 CLI와 별도 장부 산술,미청산 결과의 승격 거부를 확인한다.
- [ ] T008 [US3] scripts/sparse_opening_research.py에 replay/verify를 구현한다.
- [ ] T009 [US3] tests/integration/test_sparse_opening_research_cli.py에 지문/입력오류/덮어쓰기/재계산 검사를 작성한다.
- [ ] T010 [US3] specs/194-sparse-opening-research/results.md에 실제30파일 재생과 독립 검증을 기록한다.

## 출시
- [ ] T011 specs/194-sparse-opening-research/results.md에 전체 pytest/ruff·하네스·인계 검사 결과를 기록한다.
- [ ] T012 HANDOFF.md에 PR병합·배포 해당 여부와 전체 목표 미완료 항목을 기록한다.

의존:T001→T002→T003→US1→US2→US3→출시. 같은 구현파일은 직렬로 수정한다.
반례 설계의 읽기 전용 검토는 별도 가능하다. 첫 증분은US1이며 전체 완료는세 이야기 모두다.
실제 성과 평가 전T002의 봉인 커밋이 반드시 존재해야 한다.
