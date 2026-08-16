# Data Model: Lot-Aware Execution Proxy

## Execution Settings

- `symbol_map`: 기준 신호 종목에서 체결 종목으로 가는 대문자 1:1 매핑.
- `lot_rounding`: `floor` 또는 `nearest`. 생략 시 기존 `floor`.
- 검증: 기준 유니버스 전체를 정확히 덮고, 체결 값은 중복되지 않으며 모두 whitelist에 있어야 한다.

## Signal Target

- 기준 종목별 검증 전략 비중.
- 전략 지문과 자본 사다리 증거의 대상이다.

## Execution Target

- `symbol_map`을 적용한 체결 종목별 비중.
- 실제 KIS 보유·시세와 비교해 정수 주 주문으로 변환한다.

## Broker Snapshot

- 실제 KIS 보유 수량과 USD 매수가능현금.
- 라이브 미리보기와 실주문에서 필수다.
- 비관리 보유는 `withheld_orders`에 기록하고 자동 매도하지 않는다.

## State Transitions

`signal target -> validated 1:1 map -> execution target -> broker snapshot -> lot plan -> caps/cash/session/breaker -> preview or order`

어느 필수 단계든 실패하면 주문 제출 없이 종료한다.
