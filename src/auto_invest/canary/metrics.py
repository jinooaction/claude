"""Metric evaluator — converts BacktestRun outputs into 5 MetricResults (T013).

Per FR-C01 the canary evaluates exactly five metrics. This module owns
the conversion from raw replay/shock outputs to MetricResult values
plus the band check.

Each metric has either:

  - A numeric upper band (drawdown, latency, cost) — ``inside_band`` is
    ``observed_value <= band_upper``. Negative observed values (i.e.,
    improvements) trivially pass.
  - A "must equal" constraint (gate violations, audit-integrity) — band
    pinned to 0 by the TOML loader; ``inside_band`` is
    ``observed_value == band_must_equal``.

The decision is composed by ``CanaryMetrics.all_inside_band()`` in the
orchestrator. This module does NOT decide pass/fail by itself.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from auto_invest.canary.data_model import (
    CanaryMetrics,
    MetricResult,
    MetricSource,
    TierBands,
)


def _band_check_upper(observed: float, band_upper: float) -> bool:
    return observed <= band_upper


def _band_check_must_equal(observed: int, band_must_equal: int) -> bool:
    return observed == band_must_equal


def _to_float(value: Any) -> float:
    """Convert a Decimal / str / int / float to plain float for arithmetic.

    BacktestSummary fields are Decimal; the canary's MetricResult.observed_value
    is float (JSON-serialisable, pydantic-friendly). We lose precision below
    1e-15 but the band-check is centesimal-level so this is safe.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        return float(Decimal(value))
    return float(value)


def _drawdown_metric(
    candidate_drawdown_pct: float,
    bands: TierBands,
) -> MetricResult:
    return MetricResult(
        observed_value=candidate_drawdown_pct,
        band_upper=bands.pnl_drawdown_pct,
        band_must_equal=None,
        inside_band=_band_check_upper(candidate_drawdown_pct, bands.pnl_drawdown_pct),
        source="window_replay",
    )


def _gate_violations_metric(observed: int, source: MetricSource) -> MetricResult:
    return MetricResult(
        observed_value=float(observed),
        band_upper=None,
        band_must_equal=0,
        inside_band=_band_check_must_equal(observed, 0),
        source=source,
    )


def _audit_integrity_metric(observed: int) -> MetricResult:
    return MetricResult(
        observed_value=float(observed),
        band_upper=None,
        band_must_equal=0,
        inside_band=_band_check_must_equal(observed, 0),
        source="window_replay",
    )


def _regression_metric_unused(band_upper: float) -> MetricResult:
    """v1 placeholder for latency / cost regression — Δ between revs = 0.

    Source is ``telemetry_unused`` so downstream readers know this slot
    is reserved for v2's true two-rev comparison.
    """
    return MetricResult(
        observed_value=0.0,
        band_upper=band_upper,
        band_must_equal=None,
        inside_band=True,  # 0.0 is trivially inside any band_upper >= 0
        source="telemetry_unused",
    )


def evaluate_metrics(
    *,
    candidate_drawdown_pct: float,
    audit_integrity_count: int,
    shock_risk_gate_violations: int,
    fuzz_counterexample_count: int,
    bands: TierBands,
) -> CanaryMetrics:
    """Compose CanaryMetrics from the four atomic signals.

    Args:
        candidate_drawdown_pct: ``BacktestRun.summary.aggregate_max_drawdown_pct``
            from the window replay, as a float percentage.
        audit_integrity_count: number of DATA_QUALITY_ISSUE rows observed
            during the window replay (FR-C01 #3 — must equal 0).
        shock_risk_gate_violations: count of ``ORDER_REJECTED_BY_GATE``
            rows in synthetic-shock replay across all shock dates +
            count of property-fuzz counterexamples that violated the K1
            post-condition (both contribute to FR-C01 #2; either trips fail).
        fuzz_counterexample_count: count of FuzzCounterexample entries
            (currently rolled into ``shock_risk_gate_violations`` per
            FR-C06 all-or-nothing semantics; passed separately so the
            artefact tree can record provenance).
        bands: TierBands for the current run (L2 or L3).
    """

    total_violations = shock_risk_gate_violations + fuzz_counterexample_count

    return CanaryMetrics(
        pnl_drawdown_pct=_drawdown_metric(candidate_drawdown_pct, bands),
        risk_gate_violations=_gate_violations_metric(
            total_violations,
            source="synthetic_shock"
            if shock_risk_gate_violations > 0 or fuzz_counterexample_count == 0
            else "window_replay",
        ),
        audit_integrity_failures=_audit_integrity_metric(audit_integrity_count),
        latency_p95_regression_pct=_regression_metric_unused(
            bands.latency_p95_regression_pct
        ),
        llm_cost_regression_pct=_regression_metric_unused(
            bands.llm_cost_regression_pct
        ),
    )
