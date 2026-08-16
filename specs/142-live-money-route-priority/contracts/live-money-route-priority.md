# Live Money Route Priority Contract

## Inputs

- 표준 권위 센티넬: `automation/rebalance-live.request`
- 표준 실행 증거: `automation/rebalance-live-canary-last-run:LAST_RUN.md`
- micro 권위 센티넬: `automation/rebalance-micro-gtaa.request`
- micro 실행 증거: `automation/rebalance-micro-gtaa-last-run:LAST_RUN.md`

## Selection

각 경로를 독립 평가한 뒤 아래 순위를 적용한다.

1. `REAL_ORDER_PATH_ARMED`
2. `BLOCKED`
3. `PREVIEW_ONLY`
4. `UNKNOWN`

동률이면 표준 자본 사다리 경로를 선택한다. 무장 경로가 하나라도 있으면 비무장 보조 경로가
최상위 상태를 `PREVIEW_ONLY`로 낮출 수 없다.

## Output

`live_money_state`는 선택 경로, 상태, 주문 단계 도달 가능 여부, 자본·한도, 다음 예약 시각,
남은 안전 게이트, 최신 실행 증거를 기록한다.
