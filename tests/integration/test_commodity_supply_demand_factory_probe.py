from pathlib import Path


def test_probe_and_workflow_are_no_order_and_publish_704_trials() -> None:
    probe = Path("scripts/commodity_supply_demand_factory_probe.py").read_text()
    workflow = Path(".github/workflows/autonomous-strategy-factory.yml").read_text()
    assert "run_commodity_supply_demand_factory" in probe
    assert "run_full_gate_control_audit" in probe
    assert "auto_invest.brokers" not in probe
    assert "commodity_supply_demand_factory_probe.py" in workflow
    assert "full_gate_controls" in workflow
    assert 'global_audit_trial_count' in workflow and '= "704"' in workflow
    assert "commodity_supply_demand_factory.json" in workflow
