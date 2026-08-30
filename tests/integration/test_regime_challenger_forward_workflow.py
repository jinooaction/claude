from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_monthly_regime_observation_workflow_is_no_order_and_publishes_sidecar() -> None:
    text = (ROOT / ".github/workflows/regime-challenger-forward-observation.yml").read_text(
        encoding="utf-8"
    )

    assert "scripts/regime_adaptive_challenger_probe.py" in text
    assert "scripts/strategy_acceptance_path_audit_probe.py" in text
    assert "automation/regime-challenger-forward-last-run" in text
    assert "regime-forward-observation.json" in text
    forbidden = (
        "KIS_",
        "ssh ",
        "rebalance-once",
        "--mode live",
        "place-order",
        "submit-order",
        "capital-ladder",
        "deploy/global-trend",
    )
    assert all(token not in text for token in forbidden)
