# 검증
1. `uv run pytest tests/unit/test_public_sidecar_markdown.py tests/unit/test_security_workflow_hardening.py tests/unit/test_money_gate_alignment.py`
2. `uv run ruff check src tests scripts/redact_public_sidecar.py`
3. `uv run python scripts/agent_harness_probe.py --strict`
4. `uv run python scripts/check_handoff_facts.py`
5. PR의 기존 volume-priority 전체 회귀에서 정확 HEAD·테스트 개수·신규 반례 무생략·XML을 확인한다.
6. 실제 손상 원본은 파싱 실패 그대로 유지해야 한다. 새 유효 fixture는 비밀 없이 동일 수치로 파싱되어야 한다.
7. 병합 후 정규 발행 경로에서 새 결과를 관측한다. 보고서 갱신을 위해 자본 사다리를 수동 실행하지 않는다.
