# 빠른 검증

```bash
python -m json.tool specs/172-strategy-acceptance-path-audit/contracts/regime-forward-observation.json >/dev/null
uv run pytest tests/unit/test_forward_gate_calibration.py tests/unit/test_strategy_acceptance_path_audit.py tests/unit/test_regime_adaptive_challenger.py tests/unit/test_autonomous_work_execution.py
uv run pytest tests/integration/test_forward_gate_calibration_probe.py tests/integration/test_strategy_acceptance_path_audit_probe.py tests/integration/test_regime_challenger_forward_workflow.py
uv run ruff check src tests scripts
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

전진 관문은 `UNDERPOWERED`, 합격 경로는 `PARTIAL_COVERAGE`, 레짐 후보 전진 관찰은 현재
`OBSERVATION_WAIT`여야 한다. 어떤 결과에서도 주문·자본·라이브 설정 변경은 0이다.
