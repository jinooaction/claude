from pathlib import Path

from auto_invest.analytics.pipeline_liveness import default_specs

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-strategy-factory.yml"


def test_workflow_runs_complete_batch_without_broker_or_order_command() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/macro_strategy_factory_probe.py" in text
    assert "scripts/treasury_carry_factory_probe.py" in text
    assert "scripts/credit_spread_factory_probe.py" in text
    assert "scripts/fx_carry_factory_probe.py" in text
    assert "scripts/edge_gate_calibration_probe.py" in text
    assert "collect-public-data" in text
    assert "CPIAUCNS.csv" in text
    assert "SAHMREALTIME.csv" in text
    assert "DGS3MO.csv" in text
    assert "DGS5.csv" in text
    assert "DGS30.csv" in text
    assert "HQMCB10YR.csv" in text
    assert "HQMCB20YR.csv" in text
    assert "DEXUSAL.csv" in text
    assert "IRSTCI01USM156N.csv" in text
    assert "complete_trial_count" in text
    assert "trial_ledger.jsonl" in text
    assert "next_search.json" in text
    assert "--prior-ledger /tmp/trial_ledger_prior.jsonl" in text
    assert "scripts/recover_public_jsonl.py" in text
    assert "scripts/validate_public_factory_sidecar.py" in text
    assert "--audit-catalog audit_catalog.jsonl" in text
    assert "--allow-known-redaction-drop" in text
    assert "--macro-factory-json /tmp/macro_strategy_factory.json" in text
    assert "multiplicity_trial_count" in text
    assert ".decision.verdict" in text
    assert "next_strategy_family" in text
    assert "macro_strategy_factory.json" in text
    assert "treasury_carry_factory.json" in text
    assert "credit_spread_factory.json" in text
    assert "fx_carry_factory.json" in text
    assert "commodity_term_structure_factory.json" in text
    assert "scripts/commodity_term_structure_factory_probe.py" in text
    assert "data_fingerprint: $root.accounting_factor_data_fingerprint" in text
    assert 'prior_data_fingerprint: "turn-of-month-equity-factory-sidecar"' in text
    assert "commodity_positioning_factory.json" in text
    assert "commodity_supply_demand_factory.json" in text
    assert "scripts/commodity_supply_demand_factory_probe.py" in text
    assert "usda_crop_supply_demand_factory.json" in text
    assert "scripts/usda_crop_supply_demand_factory_probe.py" in text
    assert "energy_cross_market_factory.json" in text
    assert "scripts/energy_cross_market_factory_probe.py" in text
    assert "options_variance_risk_premium_factory.json" in text
    assert "scripts/options_variance_risk_premium_factory_probe.py" in text
    assert "turn_of_month_equity_factory.json" in text
    assert "scripts/turn_of_month_equity_factory_probe.py" in text
    assert "accounting_factor_factory.json" in text
    assert "scripts/accounting_factor_factory_probe.py" in text
    assert "real_world_gate_controls.json" in text
    assert "full_gate_controls.json" in text
    assert "audit_catalog.jsonl" in text
    assert "wc -l < /tmp/audit_catalog.jsonl" in text
    assert 'global_audit_trial_count\' /tmp/treasury_carry_factory.json)" = "576' in text
    assert 'global_audit_trial_count\' /tmp/fx_carry_factory.json)" = "656' in text
    assert (
        'global_audit_trial_count\' /tmp/usda_crop_supply_demand_factory.json)" = "720'
        in text
    )
    assert (
        'global_audit_trial_count\' /tmp/options_variance_risk_premium_factory.json)" = "752'
        in text
    )
    assert 'global_audit_trial_count\' /tmp/turn_of_month_equity_factory.json)" = "784' in text
    assert 'global_audit_trial_count\' /tmp/strategy_factory.json)" = "800' in text
    assert 'multiplicity_trial_count\' /tmp/strategy_factory.json)" = "16' in text
    assert "scripts/factory_evidence_gate.py" in text
    assert "calibrated-family-entry-v3.1" in text
    assert 'global_audit_trial_count\' /tmp/factory_evidence_v3.json)" = "800' in text
    assert "calibrated-family-risk-budget-v1" in text
    assert 'verdict\' /tmp/edge_gate_calibration.json)" = "CALIBRATED' in text
    assert "rebalance-once" not in text
    assert "KIS_" not in text
    assert "secrets.VULTR" not in text


def test_strategy_factory_is_registered_as_research_liveness() -> None:
    specs = {spec.key: spec for spec in default_specs()}
    spec = specs["autonomous-strategy-factory"]
    assert spec.branch == "automation/autonomous-strategy-factory-last-run"
    assert spec.filename == "LAST_RUN.md"
    assert spec.critical is False


def test_autonomous_work_collects_factory_decision() -> None:
    probe = (ROOT / "scripts" / "autonomous_work_execution_probe.py").read_text(encoding="utf-8")
    core = (ROOT / "src" / "auto_invest" / "analytics" / "autonomous_work_execution.py").read_text(
        encoding="utf-8"
    )
    assert '"strategy-factory"' in probe
    assert '"strategy-factory"' in core
    assert "automation/autonomous-strategy-factory-last-run:strategy_factory.json" in core
