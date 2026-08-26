# Quickstart: Calibrated Research Entry

```bash
uv run pytest tests/unit/test_edge_gate_calibration.py \
  tests/unit/test_research_family_audit.py \
  tests/unit/test_factory_evidence.py \
  tests/integration/test_factory_evidence_gate.py

uv run python scripts/edge_gate_calibration_probe.py \
  --repetitions 500 --seed 60000

uv run python scripts/factory_evidence_gate.py \
  --evidence /tmp/current_factory.json \
  --json-out /tmp/current_factory_assessment.json
```

Expected production result before release:

- raw audit rows: 752
- reconstructed research families: 17
- current option-family PBO: 0.371429
- current eligibility: false
- orders/capital changes: 0
