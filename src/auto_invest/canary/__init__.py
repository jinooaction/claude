"""Hardened canary harness — production-deploy gate (spec 007).

Under constitution v3.0.0 IX.B-2 the hardened canary is the sole acceptance
signal for autonomous production-deploy. Merges land freely via the
autonomous-workflow policy in CLAUDE.md; this package gates the bits
that actually reach the live KIS worker.

Public surface (operator + future spec 005 tuner + future spec 006 deploy
runner consume from here only):

    from auto_invest.canary import (
        run_canary,
        CanaryRun,
        CanaryMetrics,
        MetricResult,
        FuzzCounterexample,
        load_bands,
        CanaryBandsConfigError,
    )

CLI entrypoint: ``python -m auto_invest.canary {run,shock,fuzz}``.

See ``specs/007-canary-hardening/quickstart.md`` for operator onboarding.
"""

from __future__ import annotations

# Re-exports populated as the package is built out (Phase 2..5).
# Importing here keeps the public surface declared up-front so consumers
# can target it without reading the internal module layout.

__all__ = [
    "CanaryBandsConfigError",
    "CanaryMetrics",
    "CanaryRun",
    "FuzzCounterexample",
    "MetricResult",
    "load_bands",
    "run_canary",
]
