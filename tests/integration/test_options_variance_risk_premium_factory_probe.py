from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_probe_exposes_offline_sources_and_no_money_boundary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/options_variance_risk_premium_factory_probe.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--put-file" in result.stdout
    assert "--wput-file" in result.stdout
    assert "--vix-file" in result.stdout
    assert "--french-daily-file" in result.stdout
    assert "--prior-family-json" in result.stdout

    probe = Path("scripts/options_variance_risk_premium_factory_probe.py").read_text(
        encoding="utf-8"
    )
    assert "run_options_variance_risk_premium_factory" in probe
    assert "validate_options_premium_bundle" in probe
    assert "KIS_" not in probe
    assert "auto_invest.broker" not in probe


def test_workflow_keeps_options_and_turn_of_month_before_accounting_last_family() -> None:
    workflow = Path(".github/workflows/autonomous-strategy-factory.yml").read_text(encoding="utf-8")
    assert "scripts/options_variance_risk_premium_factory_probe.py" in workflow
    assert "options_variance_risk_premium_factory.json" in workflow
    assert "scripts/turn_of_month_equity_factory_probe.py" in workflow
    assert "turn_of_month_equity_factory.json" in workflow
    assert (
        'global_audit_trial_count\' /tmp/options_variance_risk_premium_factory.json)" = "752'
        in workflow
    )
    assert (
        'global_audit_trial_count\' /tmp/turn_of_month_equity_factory.json)" = "784'
        in workflow
    )
    assert "scripts/accounting_factor_factory_probe.py" in workflow
    assert "accounting_factor_factory.json" in workflow
    assert 'global_audit_trial_count\' /tmp/strategy_factory.json)" = "800' in workflow
    assert 'multiplicity_trial_count\' /tmp/strategy_factory.json)" = "16' in workflow
    assert "scripts/factory_evidence_gate.py" in workflow
    assert "calibrated-family-entry-v3.1" in workflow
    assert ".options_premium_data.complete" in workflow
    assert ".options_premium_data.sources.cboe_wput" in workflow
    assert ".selection_repair.chronology.all_folds_valid" in workflow
    assert ".selection_repair.protocol.independent_index_used_for_selection" in workflow
    assert ".objective_lanes" in workflow
    assert ".promotion_allowed" in workflow
    assert ".reference_control" in workflow
    assert ".prior_adoption_audit" in workflow
    assert "if: success()" in workflow
