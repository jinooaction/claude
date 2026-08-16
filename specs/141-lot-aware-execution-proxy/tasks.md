# Tasks: Lot-Aware Execution Proxy

- [x] T001 새 등급 4 명세와 조사 기록을 `specs/141-lot-aware-execution-proxy/`에 만든다.
- [x] T002 [US3] `[execution]` 설정을 엄격히 읽고 검증하는 로더를 `src/auto_invest/cli.py`에 구현한다.
- [x] T003 [US1] 선택적 nearest 정수 주 산정을 `src/auto_invest/strategy/rebalance.py`에 구현한다.
- [x] T004 [US1] 기준 신호를 체결 종목으로 매핑하는 실행 경로를 `src/auto_invest/execution/rebalancer.py`에 구현한다.
- [x] T005 [US2] 라이브 설정에 저가 ETF whitelist와 account-wide 실제 스냅샷을 `deploy/canary-live-portfolio.toml`에 적용한다.
- [x] T006 [US2] 미리보기와 실주문 명령을 `.github/workflows/rebalance-live-canary.yml`에서 동일한 account-wide 경로로 바꾼다.
- [x] T007 [P] [US1] 정수 주와 매핑 회귀를 `tests/integration/test_spec_032_live_rebalancer.py`에 추가한다.
- [x] T008 [P] [US3] 설정·워크플로 안전 불변식을 `tests/unit/`에 추가한다.
- [x] T009 전체 pytest, ruff, diff, 하네스, HANDOFF 사실, PR 품질 관문을 통과한다.
- [x] T010 안전 경계 커밋, PR, 자동 머지와 배포를 완료한다.
- [x] T011 배포 후 KIS 미리보기에서 실제 계좌·현금·1주 이상 계획을 확인한다.
- [ ] T012 미국 정규장에서 첫 주문·체결·잔고·감사 로그를 확인한다.
- [x] T013 [US4] 실주문·체결 동기화·사후 측정의 실패 전파와 sidecar 증거를 보강한다.
