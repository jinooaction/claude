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
