# Execution Proxy Contract

## Portfolio TOML

```toml
[execution]
symbol_map = { SPY = "SPYM", IEF = "IEF", GLD = "GLDM" }
lot_rounding = "nearest"
```

- 매핑 키는 `[portfolio].universe`와 정확히 같아야 한다.
- 매핑 값은 서로 달라야 하고 `[whitelist].symbols`에 모두 있어야 한다.
- 신호 계산은 키 종목의 저장 가격 이력을 사용한다.
- 주문 시세·보유·주문 종목은 값 종목을 사용한다.

## Live Command

미리보기와 실주문은 모두 `--account-wide`를 사용한다. 미리보기만 `--dry-run`, 실주문만
`--mode live --confirm-live`를 사용한다.

## Evidence

JSON 결과는 `signal_target_weights`, `target_weights`, `execution_symbol_map`,
`account_wide`, `purchasable_cash_usd`, `required_cash_usd`, 주문 결과와 보류 주문을 포함한다.

실주문·체결 동기화·사후 측정의 SSH 종료 코드는 각 단계 결과에 그대로 반영한다. 실주문 뒤
`fills --sync`를 최대 세 번 실행해 KIS 체결을 추가-전용 장부에 반영하고 열린 주문·최근 체결을
출력한다. 어느 단계가 실패해도 마지막 sidecar는 `LIVE`, 체결 동기화, 사후 측정 결과와 가용한
stdout·stderr를 발행한다.
