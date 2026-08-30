# 빠른 검증

## 1. 계약 형식

```bash
python -m json.tool specs/174-accounting-cross-sectional-factors/contracts/accounting-factor-preregistration.json >/dev/null
python -m json.tool specs/174-accounting-cross-sectional-factors/contracts/accounting-factor-result.schema.json >/dev/null
```

## 2. 좁은 회귀시험

```bash
uv run pytest \
  tests/unit/test_accounting_factor_factory.py \
  tests/unit/test_research_family_audit.py \
  tests/unit/test_factory_evidence.py \
  tests/integration/test_accounting_factor_factory_probe.py \
  tests/integration/test_strategy_factory_workflow.py
```

## 3. 공식 자료 생산 재생

```bash
uv run python scripts/accounting_factor_factory_probe.py \
  --prior-factory-json /tmp/turn_of_month_equity_factory.json \
  --calibration-json /tmp/edge_gate_calibration.json \
  --code-commit "$(git rev-parse HEAD)" \
  --json-out /tmp/accounting_factor_factory.json \
  --summary-out /tmp/ACCOUNTING_FACTOR_LAST_RUN.md
```

결과와 무관하게 후보 16개, 전역 감사 800행, 전략 가족 20개, 프로그램 오합격 상한 0.20이어야
한다. 선택 배포 설정은 `null`, 실행 동등성과 승격은 false, 주문·자본·라이브 변경은 0건이어야 한다.

## 4. 전체 완료 관문

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```
