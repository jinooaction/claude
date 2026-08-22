# Quickstart

```bash
uv run pytest tests/unit/test_strategy_measurement_contract.py \
  tests/unit/test_portfolio_growth.py \
  tests/unit/test_low_turnover_daily_ml.py
uv run ruff check src tests
```

검증할 핵심 출력:

1. 역사 외부 보유 청산 체결이 전략 손익에서 제외된다.
2. 새 계약 이전 NAV는 유효 관측 수에서 제외된다.
3. 복구 준비도는 주문과 halt 변경 없이 판정만 낸다.
4. 저회전 후보는 10/25/50bp 비용과 회전율 감소를 함께 보고한다.
