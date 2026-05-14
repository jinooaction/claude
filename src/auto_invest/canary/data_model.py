"""Data models for the canary harness (T007).

Mirrors `specs/007-canary-hardening/data-model.md`. All models are frozen
pydantic v2 with `extra="forbid"` so the on-disk JSON schema cannot
silently drift.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MetricId = Literal[
    "pnl_drawdown_pct",
    "risk_gate_violations",
    "audit_integrity_failures",
    "latency_p95_regression_pct",
    "llm_cost_regression_pct",
]

KernelGroup = Literal["K1", "K2", "K3", "K4", "K5", "K6", "K_meta"]

Tier = Literal["L2", "L3"]

OutcomeStatus = Literal["passed", "failed", "in_progress"]

MetricSource = Literal["window_replay", "synthetic_shock", "telemetry_unused"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TierBands(_Frozen):
    """Acceptance bands for one tier, loaded from `config/canary_bands.toml`."""

    trading_days: int
    pnl_drawdown_pct: float
    risk_gate_violations: int  # MUST be 0 (loader enforces)
    audit_integrity_failures: int  # MUST be 0 (loader enforces)
    latency_p95_regression_pct: float
    llm_cost_regression_pct: float


class MetricResult(_Frozen):
    """One row in `metrics.csv` and one entry in `canary-run.json`.metrics."""

    observed_value: float
    band_upper: float | None = None
    band_must_equal: int | None = None
    inside_band: bool
    source: MetricSource


class CanaryMetrics(_Frozen):
    """The five FR-C01 metrics. ``inside_band`` is the AND of the five."""

    pnl_drawdown_pct: MetricResult
    risk_gate_violations: MetricResult
    audit_integrity_failures: MetricResult
    latency_p95_regression_pct: MetricResult
    llm_cost_regression_pct: MetricResult

    def all_inside_band(self) -> bool:
        return (
            self.pnl_drawdown_pct.inside_band
            and self.risk_gate_violations.inside_band
            and self.audit_integrity_failures.inside_band
            and self.latency_p95_regression_pct.inside_band
            and self.llm_cost_regression_pct.inside_band
        )

    def failing_metric_ids(self) -> list[str]:
        out: list[str] = []
        if not self.pnl_drawdown_pct.inside_band:
            out.append("pnl_drawdown_pct")
        if not self.risk_gate_violations.inside_band:
            out.append("risk_gate_violations")
        if not self.audit_integrity_failures.inside_band:
            out.append("audit_integrity_failures")
        if not self.latency_p95_regression_pct.inside_band:
            out.append("latency_p95_regression_pct")
        if not self.llm_cost_regression_pct.inside_band:
            out.append("llm_cost_regression_pct")
        return sorted(out)


class KernelTouch(_Frozen):
    """One entry per touched kernel group in the candidate diff."""

    group: KernelGroup
    files: list[str]  # sorted lexicographically by the producer


class FuzzCounterexample(_Frozen):
    """One row in `property-fuzz/counterexamples.json`."""

    seed: int
    shrunk_input: dict[str, Any]
    assertion_failed: str
    gate_decision: dict[str, Any]


class SeedBundle(_Frozen):
    """Captured at canary start; preserves SC-C04 reproducibility."""

    hypothesis_database_seed: int
    hypothesis_iterations: int
    synthetic_shock_dates: list[date]
    quarterly_opex_resolved_for: date


class CanaryRun(_Frozen):
    """The canonical on-disk artefact (`canary-run.json`)."""

    canary_run_id: uuid.UUID
    candidate_rev: str
    baseline_rev: str
    tier: Tier
    window_trading_days: int
    window_start_date: date
    window_end_date: date
    started_at: datetime
    finished_at: datetime | None = None
    outcome: OutcomeStatus = "in_progress"
    failing_metrics: list[str] = Field(default_factory=list)
    kernel_touches: list[KernelTouch] = Field(default_factory=list)
    metrics: CanaryMetrics | None = None
    seed_bundle: SeedBundle | None = None
