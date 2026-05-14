"""Spec 007 T014 — five-metric evaluator unit tests."""

from __future__ import annotations

import pytest

from auto_invest.canary.bands import load_bands
from auto_invest.canary.data_model import TierBands
from auto_invest.canary.metrics import evaluate_metrics


@pytest.fixture
def l2_bands() -> TierBands:
    bands = load_bands()
    return bands["L2"]


@pytest.fixture
def l3_bands() -> TierBands:
    bands = load_bands()
    return bands["L3"]


# ---------------------------------------------------------- drawdown


def test_drawdown_within_band_passes(l2_bands: TierBands) -> None:
    m = evaluate_metrics(
        candidate_drawdown_pct=1.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert m.pnl_drawdown_pct.inside_band
    assert m.all_inside_band()


def test_drawdown_above_band_fails(l2_bands: TierBands) -> None:
    m = evaluate_metrics(
        candidate_drawdown_pct=3.5,  # above 3.0 band
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert not m.pnl_drawdown_pct.inside_band
    assert not m.all_inside_band()
    assert "pnl_drawdown_pct" in m.failing_metric_ids()


def test_drawdown_at_band_boundary_passes(l2_bands: TierBands) -> None:
    """Edge: equal to band is inside (FR-C01 uses ``<=`` semantics)."""
    m = evaluate_metrics(
        candidate_drawdown_pct=3.0,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert m.pnl_drawdown_pct.inside_band


def test_l3_drawdown_band_tighter_than_l2(
    l2_bands: TierBands, l3_bands: TierBands
) -> None:
    """Defaults: L3 = 2.0%, L2 = 3.0%. A 2.5% drawdown passes L2 fails L3."""
    m_l2 = evaluate_metrics(
        candidate_drawdown_pct=2.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    m_l3 = evaluate_metrics(
        candidate_drawdown_pct=2.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l3_bands,
    )
    assert m_l2.all_inside_band()
    assert not m_l3.all_inside_band()


# ---------------------------------------------------------- must-equal-0 metrics


def test_risk_gate_violations_must_be_zero(l2_bands: TierBands) -> None:
    m = evaluate_metrics(
        candidate_drawdown_pct=0.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=1,  # one violation breaks it
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert not m.risk_gate_violations.inside_band
    assert m.risk_gate_violations.band_must_equal == 0
    assert m.risk_gate_violations.band_upper is None
    assert "risk_gate_violations" in m.failing_metric_ids()


def test_audit_integrity_failures_must_be_zero(l2_bands: TierBands) -> None:
    m = evaluate_metrics(
        candidate_drawdown_pct=0.5,
        audit_integrity_count=1,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert not m.audit_integrity_failures.inside_band
    assert "audit_integrity_failures" in m.failing_metric_ids()


def test_fuzz_counterexample_counts_as_gate_violation(l2_bands: TierBands) -> None:
    """FR-C06 all-or-nothing: any fuzz counterexample fails the canary via
    the gate-violations metric (the SHARED count, not a separate metric).
    """
    m = evaluate_metrics(
        candidate_drawdown_pct=0.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=2,
        bands=l2_bands,
    )
    assert not m.risk_gate_violations.inside_band
    assert m.risk_gate_violations.observed_value == 2.0


# ---------------------------------------------------------- Δ-style placeholders


def test_v1_latency_regression_is_zero_telemetry_unused(l2_bands: TierBands) -> None:
    m = evaluate_metrics(
        candidate_drawdown_pct=0.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert m.latency_p95_regression_pct.observed_value == 0.0
    assert m.latency_p95_regression_pct.source == "telemetry_unused"
    assert m.latency_p95_regression_pct.inside_band
    assert m.latency_p95_regression_pct.band_upper == pytest.approx(
        l2_bands.latency_p95_regression_pct
    )


def test_v1_llm_cost_regression_is_zero_telemetry_unused(l2_bands: TierBands) -> None:
    m = evaluate_metrics(
        candidate_drawdown_pct=0.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert m.llm_cost_regression_pct.observed_value == 0.0
    assert m.llm_cost_regression_pct.source == "telemetry_unused"
    assert m.llm_cost_regression_pct.inside_band


# ---------------------------------------------------------- FR-C06 all-or-nothing


def test_four_of_five_does_not_pass(l2_bands: TierBands) -> None:
    """FR-C06: no 4-of-5 carve-out (R-C6).

    Drawdown out of band, all other metrics clean → fail.
    """
    m = evaluate_metrics(
        candidate_drawdown_pct=5.0,  # well above 3.0
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert not m.all_inside_band()
    assert m.failing_metric_ids() == ["pnl_drawdown_pct"]


def test_negative_drawdown_passes(l2_bands: TierBands) -> None:
    """A negative drawdown (i.e. an improvement) trivially passes."""
    m = evaluate_metrics(
        candidate_drawdown_pct=-0.5,
        audit_integrity_count=0,
        shock_risk_gate_violations=0,
        fuzz_counterexample_count=0,
        bands=l2_bands,
    )
    assert m.pnl_drawdown_pct.inside_band


def test_all_five_failing_reports_all_failing(l2_bands: TierBands) -> None:
    m = evaluate_metrics(
        candidate_drawdown_pct=5.0,
        audit_integrity_count=3,
        shock_risk_gate_violations=2,
        fuzz_counterexample_count=1,
        bands=l2_bands,
    )
    failing = m.failing_metric_ids()
    # latency / cost still pass because v1 Δ is 0
    assert "pnl_drawdown_pct" in failing
    assert "risk_gate_violations" in failing
    assert "audit_integrity_failures" in failing
    assert "latency_p95_regression_pct" not in failing
    assert "llm_cost_regression_pct" not in failing
