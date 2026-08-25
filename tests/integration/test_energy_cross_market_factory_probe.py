from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_probe_exposes_offline_inputs_and_no_money_boundary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/energy_cross_market_factory_probe.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--eia-data-dir" in result.stdout
    assert "--french-industry-file" in result.stdout
    assert "--prior-factory-json" in result.stdout
    assert "--controls-json" in result.stdout

    probe = Path("scripts/energy_cross_market_factory_probe.py").read_text(
        encoding="utf-8"
    )
    assert "run_energy_cross_market_factory" in probe
    assert "validate_energy_cross_market_bundle" in probe
    assert "KIS_" not in probe
    assert "auto_invest.broker" not in probe


def test_strategy_factory_workflow_preserves_energy_before_options_family() -> None:
    workflow = Path(".github/workflows/autonomous-strategy-factory.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/energy_cross_market_factory_probe.py" in workflow
    assert "energy_cross_market_factory.json" in workflow
    assert (
        'global_audit_trial_count\' /tmp/energy_cross_market_factory.json)" = "736'
        in workflow
    )
    assert (
        'multiplicity_trial_count\' /tmp/energy_cross_market_factory.json)" = "16'
        in workflow
    )
    assert "--prior-factory-json /tmp/energy_cross_market_factory.json" in workflow
    assert "if: success()" in workflow
    assert ".energy_cross_market_data.complete" in workflow
    assert ".model_chronology.passed" in workflow
