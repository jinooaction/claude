# 검증
1. `uv run pytest tests/unit/test_intraday_execution.py tests/integration/test_intraday_execution_contract.py`
2. `uv run python scripts/intraday_execution.py rehearse`
3. `uv run pytest`, `uv run ruff check src tests`
4. strict harness, HANDOFF사실검사, PR품질관문.
기존181 KIS서버 timer는 유지한다. rehearsal은 네트워크·실제키를 사용하지 않는다.
