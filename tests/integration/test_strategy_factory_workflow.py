from pathlib import Path

from auto_invest.analytics.pipeline_liveness import default_specs

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-strategy-factory.yml"


def test_workflow_runs_complete_batch_without_broker_or_order_command() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/macro_strategy_factory_probe.py" in text
    assert "scripts/treasury_carry_factory_probe.py" in text
    assert "scripts/edge_gate_calibration_probe.py" in text
    assert "collect-public-data" in text
    assert "CPIAUCNS.csv" in text
    assert "SAHMREALTIME.csv" in text
    assert "DGS3MO.csv" in text
    assert "DGS5.csv" in text
    assert "DGS30.csv" in text
    assert "complete_trial_count" in text
    assert "trial_ledger.jsonl" in text
    assert "next_search.json" in text
    assert "--prior-ledger /tmp/trial_ledger_prior.jsonl" in text
    assert "multiplicity_trial_count" in text
    assert ".decision.verdict" in text
    assert "next_strategy_family" in text
    assert "macro_strategy_factory.json" in text
    assert "treasury_carry_factory.json" in text
    assert 'global_audit_trial_count\' /tmp/strategy_factory.json)\" = \"576' in text
    assert 'multiplicity_trial_count\' /tmp/strategy_factory.json)\" = \"64' in text
    assert 'verdict\' /tmp/edge_gate_calibration.json)\" = \"CALIBRATED' in text
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
