from __future__ import annotations

from pathlib import Path


def test_probe_and_workflow_are_no_order_and_publish_688_trials() -> None:
    probe = Path("scripts/commodity_positioning_factory_probe.py").read_text()
    workflow = Path(".github/workflows/autonomous-strategy-factory.yml").read_text()
    assert "run_commodity_positioning_factory" in probe
    assert "auto_invest.brokers" not in probe
    assert "commodity_positioning_factory_probe.py" in workflow
    assert "real_world_gate_controls" in workflow
    assert 'global_audit_trial_count' in workflow and '= "688"' in workflow
    assert "commodity_positioning_factory.json" in workflow
