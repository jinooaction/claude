from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_probe_exposes_offline_inputs_and_no_money_boundary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/usda_crop_supply_demand_factory_probe.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--wasde-index-dir" in result.stdout
    assert "--wasde-data-dir" in result.stdout
    assert "--prior-factory-json" in result.stdout
    assert "--controls-json" in result.stdout

    probe = Path("scripts/usda_crop_supply_demand_factory_probe.py").read_text()
    assert "run_usda_crop_supply_demand_factory" in probe
    assert "KIS_" not in probe
    assert "auto_invest.brokers" not in probe


def test_strategy_factory_workflow_registers_usda_as_canonical_last_family() -> None:
    workflow = Path(".github/workflows/autonomous-strategy-factory.yml").read_text()
    assert "scripts/usda_crop_supply_demand_factory_probe.py" in workflow
    assert "usda_crop_supply_demand_factory.json" in workflow
    assert 'global_audit_trial_count\' /tmp/strategy_factory.json)" = "720' in workflow
    assert 'multiplicity_trial_count\' /tmp/strategy_factory.json)" = "16' in workflow
