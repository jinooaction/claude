from auto_invest.analytics.edge_gate_calibration import run_edge_gate_calibration


def test_revised_gate_controls_false_acceptance_and_detects_planted_edge() -> None:
    report = run_edge_gate_calibration(
        seed=60_000,
        repetitions=200,
        timestamp_utc="2026-08-23T00:00:00Z",
        code_commit="abc123",
    )
    assert report["verdict"] == "CALIBRATED"
    assert report["revised"]["false_acceptance_rate"] <= 0.05
    assert report["revised"]["detection_rate"] >= 0.80
    assert report["legacy"]["detection_rate"] < report["revised"]["detection_rate"]
    assert report["thresholds"] == {
        "development_dsr_diagnostic_min": 0.95,
        "development_pbo_diagnostic_max": 0.1,
        "holdout_psr_min": 0.95,
        "paper_psr_min": 0.8,
    }
    assert set(report["family_calibrations"]) == {"16", "64"}
    for calibration in report["family_calibrations"].values():
        assert calibration["live_calibrated"] is True
        assert calibration["null_false_acceptance_rate"] <= 0.05
        assert calibration["target_live_detection_rate"] >= 0.80
        assert set(calibration["power_curve"]) == {
            "0.20",
            "0.30",
            "0.40",
            "0.50",
            "0.60",
            "0.80",
        }
        assert calibration["power_curve"]["0.40"]["live_detection_rate"] < 0.80
        assert (
            calibration["power_curve"]["0.40"]["paper_admission_rate"]
            > calibration["power_curve"]["0.40"]["live_detection_rate"]
        )


def test_calibration_is_deterministic_for_fixed_inputs() -> None:
    kwargs = {
        "seed": 60_000,
        "repetitions": 200,
        "timestamp_utc": "2026-08-23T00:00:00Z",
        "code_commit": "abc123",
    }
    assert run_edge_gate_calibration(**kwargs) == run_edge_gate_calibration(**kwargs)
