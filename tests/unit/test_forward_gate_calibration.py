from __future__ import annotations

from auto_invest.analytics.forward_gate_calibration import (
    CALIBRATED,
    run_forward_gate_calibration,
)


def test_paired_gate_is_calibrated_and_has_more_power_than_legacy() -> None:
    report = run_forward_gate_calibration(seed=159_001, repetitions=2_000)

    assert report["verdict"] == CALIBRATED
    null_paired = report["null"]["paired_active_return"]
    planted_paired = report["planted_edge"]["paired_active_return"]
    planted_legacy = report["planted_edge"]["legacy_fixed_benchmark_sharpe"]
    assert 0.17 <= null_paired["paper_acceptance_rate"] <= 0.23
    assert null_paired["live_acceptance_rate"] <= 0.06
    assert (
        planted_paired["paper_acceptance_rate"]
        > planted_legacy["paper_acceptance_rate"]
    )
    assert all(report["checks"].values())
    assert report["safety"] == [
        "simulation only",
        "no broker API",
        "no orders",
        "no capital change",
    ]


def test_paired_gate_calibration_is_deterministic() -> None:
    kwargs = {"seed": 159_001, "repetitions": 2_000, "code_commit": "abc123"}
    assert run_forward_gate_calibration(**kwargs) == run_forward_gate_calibration(**kwargs)
