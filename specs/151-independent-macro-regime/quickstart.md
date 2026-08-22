# Quickstart: 독립 거시 레짐 전략군

## 구현 전 확인

1. `.specify/feature.json`이 스펙 151을 가리키는지 확인한다.
2. 사전 등록 후보 수가 네 전략군 x 16 = 64인지 확인한다.
3. 탐색 재생 문법이 64 x 3 = 192인지 확인한다.
4. 현재 `armed:false`, 단 0, 자본 0인지 확인한다.

## 권장 검증 순서

```bash
uv run pytest -q tests/unit/test_macro_regime.py tests/unit/test_macro_strategy_factory.py
uv run pytest -q tests/integration/test_macro_strategy_factory_probe.py
uv run ruff check src tests scripts
uv run pytest -q
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

## 성공 판독

- 자료 깊이와 발표 지연 관문이 모두 PASS다.
- 192개 탐색 재생과 64개 공식 후보가 완전하다.
- 누적 시도 수는 512다.
- 모든 스펙 150 관문이 PASS일 때만 `FACTORY_EDGE`다.
- 그 외 모든 경우 자본 0·주문 0을 유지한다.
