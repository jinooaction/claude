# 빠른 검증

## 1. 계약 형식

```bash
python -m json.tool specs/173-independent-turn-of-month-edge/contracts/turn-of-month-contract.json >/dev/null
python -m json.tool specs/173-independent-turn-of-month-edge/contracts/forward-calibration-consumer.json >/dev/null
python -m json.tool specs/173-independent-turn-of-month-edge/contracts/turn-of-month-result.schema.json >/dev/null
```

## 2. 좁은 회귀 시험

```bash
uv run pytest \
  tests/unit/test_forward_gate_calibration.py \
  tests/unit/test_backtest_anchored.py \
  tests/unit/test_capital_ladder.py \
  tests/unit/test_turn_of_month_equity_factory.py \
  tests/unit/test_research_family_audit.py \
  tests/integration/test_ladder_decide_cli.py \
  tests/integration/test_forward_edge_autoarm_workflow.py \
  tests/integration/test_turn_of_month_equity_factory_probe.py \
  tests/integration/test_strategy_factory_workflow.py
```

## 3. 공식 자료 생산 재생

```bash
uv run python scripts/edge_gate_calibration_probe.py \
  --seed 60000 --repetitions 500 --code-commit "$(git rev-parse HEAD)" \
  --json-out /tmp/edge_gate_calibration.json
uv run python scripts/turn_of_month_equity_factory_probe.py \
  --prior-factory-json /tmp/strategy_factory_before_calendar.json \
  --released-regime-json specs/171-parallel-regime-edge-challenger/production-result.json \
  --calibration-json /tmp/edge_gate_calibration.json \
  --code-commit "$(git rev-parse HEAD)" \
  --json-out /tmp/turn_of_month_equity_factory.json \
  --summary-out /tmp/TURN_OF_MONTH_LAST_RUN.md
```

결과가 무엇이든 후보는 16개, 전역 감사 행은 784개, 가족은 19개여야 한다. 선택 배포 설정은
`null`, `research_live_parity=false`, `promotion_allowed=false`, 주문·자본·라이브 변경은 0이어야 한다.

## 4. 전체 완료 관문

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```
