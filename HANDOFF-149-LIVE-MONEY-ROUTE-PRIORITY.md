# HANDOFF-149 - Live Money Route Priority

## 결론

#624로 실제 주문 가능 경로의 최상위 표시를 바로잡았다. 표준 자본 사다리 단 1·293달러 경로가
`REAL_ORDER_PATH_ARMED`로 보이고, 파생 준비도도 `CAPITAL_ARMABLE`로 일치한다. 서버 배포까지
끝났지만 실제 주문·체결·수익은 아직 0이므로 전체 수익 목표는 완료가 아니다.

## 현재 사실

- main: `bb8f200` (#624), 기능 커밋 `679c008`
- deploy run: `31921324439`, success
- deploy correlation_id: `75745d159c83c53beb4b31567ac796a3`
- money-path run: `31921324379`, `REAL_ORDER_PATH_ARMED`
- capital-path-readiness run: `31921361671`, `CAPITAL_ARMABLE`
- 센티넬: `armed:true`, rung 1, `capital_usd:293`, account NAV 1466.83달러
- 마지막 미리보기: `SPYM` 1주 + `GLDM` 1주, 계획 매수 178.32달러
- 실제 주문·체결·수익: 0

## #624가 고친 경로

1. `automation/rebalance-live.request`와 최신 live-canary sidecar를 표준 경로 권위 증거로 읽는다.
2. 표준 자본 사다리와 micro 경로를 독립 평가한다.
3. `REAL_ORDER_PATH_ARMED > BLOCKED > PREVIEW_ONLY > UNKNOWN` 순으로 최상위 경로를 고른다.
4. 표준 센티넬과 sidecar 무장이 다르거나 빠지면 실주문 가능으로 추정하지 않고 차단한다.
5. 주문·자본·전략·허용 목록·손실 제한은 바꾸지 않는다.

## 다음 실행

- 예약: `0 15 * * 1-5`, 다음 실행은 2026-08-18 00:00 KST.
- production 환경은 `main`만 허용하고 required reviewer `jinooaction` 승인을 요구한다.
- 승인 뒤 같은 run에서 production, 비-push, 정규장, 현금 1% 여유, 손실 브레이커, K1/K2를
  모두 통과해야 주문 단계에 들어간다.
- 주문 뒤 sidecar의 KIS 주문 식별자·상태, 체결 동기화, 열린 주문, 최근 체결, 잔고·NAV,
  추가-전용 감사 로그, ORANY 자동 매도 0건을 대조한다.
- 지정가가 체결되지 않으면 완료로 판정하지 않고 KIS smoke와 후속 동기화에서 상태를 추적한다.

## 검증과 되돌림

- 연관 회귀 169 passed
- 전체 2833 passed, 6 skipped
- ruff, diff, HANDOFF 사실 검사, 엄격 하네스 14/14, PR 품질 관문 통과
- 이상 표시가 생기면 #624 merge commit `bb8f200`을 새 PR에서 revert한다. 감사 로그와 계좌 기록은
  삭제하지 않으며 센티넬·sidecar 불일치는 계속 실패 폐쇄한다.
