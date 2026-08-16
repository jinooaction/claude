# HANDOFF-150 - Live Canary Gateway And Profit Evidence

## 결론

#626으로 실제 주문이 제한 SSH 서버에서 거부될 구조를 production 전용 서명 관문으로 교체했고,
체결부터 최초 양의 실계좌 손익까지 자동 추적하는 증거 연쇄를 배포했다. 현재 경로는 무장됐지만
실제 체결 0건·총손익 0달러이므로 수익 목표는 아직 완료가 아니다.

## 현재 권위 사실

- main: `5d20ea8` (#626), 안전 경계 기능 커밋 `86f56b2`
- deploy run: `31922602120`, success
- live-profit run: `31922633808`, `NO_FILLS_YET`
- money-path run: `31922655716`, `REAL_ORDER_PATH_ARMED`
- capital-path-readiness run: `31922666593`, `CAPITAL_ARMABLE`
- KIS smoke run: `31922634930`, 5/5 success
- 실계좌: 현금 934.27달러, NAV 1466.83달러, ORANY 28주, 열린 미체결 0건
- 센티넬: `armed:true`, rung 1, `capital_usd:293`
- 실제 주문·체결·수익: 0건·0건·0달러

## #626이 완성한 경로

1. production 환경 전용 Ed25519 개인키가 저장소·워크플로·run·commit·자본·만료·nonce를 서명한다.
2. 서버 root 소유 helper가 공개키, 10분 만료, nonce 재사용, 센티넬, rung/NAV, 배포 코드 정합을 실패 폐쇄로 검증한다.
3. 검증 뒤 기존 `rebalance-once --mode live --confirm-live --account-wide`를 호출하므로 K1/K2, 정규장, 현금, 손실 브레이커, 감사 로그는 그대로 적용된다.
4. 주문 불가능한 고정 명령이 KIS 체결을 동기화하고 기존 성과 엔진으로 live 손익을 측정한다.
5. 체결 1건 이상·결측 0·경고 0·총손익 양수일 때만 최초 수익을 기록하며 이후 현재 손익이 음수가 돼도 최초 증거는 보존한다.
6. live-canary 완료가 live-profit을, 그 완료가 money-path를, 그 완료가 capital readiness를 자동 실행한다.

## 다음 실행과 완료 기준

- 예약: `2026-08-17T15:00:00Z` = `2026-08-18 00:00 KST`.
- production environment required reviewer `jinooaction` 승인 뒤 비-push·미국 정규장·현금 1% 여유·손실 브레이커·K1/K2를 모두 통과해야 주문한다.
- 같은 run과 후속 `15:30/17:30/19:30 UTC` 관측에서 주문 상태, 체결, 열린 주문, 잔고, 감사 로그, `profit_evidence.json`을 확인한다.
- `first_profit_observed=true`, `fills_count>0`, 결측·경고 0, 최초 총손익 양수가 권위 sidecar에 기록될 때만 T017과 전체 목표를 완료한다.
- 지정가 미체결이나 손실이면 기준을 바꾸거나 추가 주문을 강제하지 않고 예약 관측을 계속한다.

## 검증과 되돌림

- 전체 2853 passed, 6 skipped
- ruff, bash, YAML, diff, HANDOFF 사실 검사, 엄격 하네스 14/14, PR 품질 관문 통과
- 이상 시 #626 merge commit `5d20ea8`을 새 PR에서 revert한다. production secret은 별도로 폐기하고 공개키를 교체한다.
- 감사 로그, 주문·체결 기록, 최초 수익 증거는 삭제하거나 과거 상태로 덮어쓰지 않는다.
