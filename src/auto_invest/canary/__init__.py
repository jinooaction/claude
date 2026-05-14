"""Hardened canary harness — production-deploy gate (spec 007).

Under constitution v3.0.0 IX.B-2 the hardened canary is the sole acceptance
signal for autonomous production-deploy. Merges land freely via the
autonomous-workflow policy in CLAUDE.md; this package gates the bits
that actually reach the live KIS worker.

Public surface (operator + future spec 005 tuner + future spec 006 deploy
runner consume from here only). CLI entrypoint:
``python -m auto_invest.canary {run,shock,fuzz}``.

See ``specs/007-canary-hardening/quickstart.md`` for operator onboarding.
"""

from __future__ import annotations

from auto_invest.canary.bands import CanaryBandsConfigError, load_bands
from auto_invest.canary.data_model import (
    CanaryMetrics,
    CanaryRun,
    FuzzCounterexample,
    KernelTouch,
    MetricResult,
    SeedBundle,
    TierBands,
)
from auto_invest.canary.run import (
    EXIT_COVERAGE,
    EXIT_FAILED,
    EXIT_INTERNAL,
    EXIT_OK,
    EXIT_USAGE,
    CanaryOptions,
    CanaryRunOutcome,
    run_canary,
)

__all__ = [
    "EXIT_COVERAGE",
    "EXIT_FAILED",
    "EXIT_INTERNAL",
    "EXIT_OK",
    "EXIT_USAGE",
    "CanaryBandsConfigError",
    "CanaryMetrics",
    "CanaryOptions",
    "CanaryRun",
    "CanaryRunOutcome",
    "FuzzCounterexample",
    "KernelTouch",
    "MetricResult",
    "SeedBundle",
    "TierBands",
    "load_bands",
    "run_canary",
]
