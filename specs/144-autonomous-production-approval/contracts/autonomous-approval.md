# Contract: Autonomous Production Approval

## Inputs

- preview `armed == true`
- preview `blocked != true`
- 유효한 `capital`
- `github.ref == refs/heads/main`
- `github.event_name`이 `schedule` 또는 `workflow_dispatch`

## Output

- `schedule` -> `decision=scheduled-real-order`
- `workflow_dispatch` -> `decision=manual-no-order-preflight`

그 밖의 입력은 성공 출력을 만들지 않는다. 이 job은 production 환경을 선언하지 않으며 개인 서명키를 읽지 않는다.

## Consumer

`live_portfolio_canary_real_orders`는 승인 job 결과가 `success`이고 decision이 두 허용값 중 하나일 때만
production 환경에 진입한다. 내부에서 decision을 다시 검증한 후 요청을 서명한다. 실제 주문 gateway는
오직 `scheduled-real-order`에 대응하는 `live-canary-order`다. 수동 실행은 `live-canary-verify-order`다.

## Environment Policy

GitHub `production` 환경은 required reviewer가 0명이고 custom branch policy는 `main` 하나여야 한다.
`LIVE_ORDER_SIGNING_KEY`는 이 환경의 비밀값으로 유지한다.

