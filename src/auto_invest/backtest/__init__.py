"""Backtest engine (spec 008) — deterministic offline replay.

Public surface assembled as submodules become available. The engine
drives existing Worker.tick / risk-gate / order-router code against
historical OHLCV bars, with a fully in-memory broker and an
LLM-call-disallowed judgment stub. See specs/008-backtest-engine/
for the spec, plan, research, data-model, and contracts.

Safety contracts (spec FR refs):
  - FR-B02: WallClockGuard detects datetime.now() reads during replay.
  - FR-B06: BacktestBroker is the ONLY broker adapter wired in replay.
  - FR-B08: JudgmentStub is the ONLY LLM call site wired in replay.
  - FR-B12: kernel_pre_flight refuses to run on a kernel-touched tree.
  - FR-B15: byte-identical determinism across runs.
"""

from __future__ import annotations

from .broker_mock import (
    ADAPTER_ID,
    BacktestBroker,
    BacktestLiveBrokerLeakError,
)
from .clock import ReplayClock, WallClockLeakError, wall_clock_guard
from .data_model import (
    BacktestRun,
    BacktestSummary,
    OHLCVBar,
    RuleBacktestResult,
    SyntheticShockDay,
    canonicalise_decimal,
)
from .data_source import CSVDataSource, HistoricalDataSource
from .ingest import IngestError, IngestResult, ingest_history
from .judgment_stub import (
    BACKTEST_MODE_ENV,
    BacktestJudgmentLeakError,
    JudgmentStub,
    guard_no_real_llm,
)
from .metrics import (
    aggregate_metrics,
    max_drawdown_pct,
    sharpe_ratio,
    total_return_pct,
)
from .replay import ReplayResult, replay
from .report import (
    KernelGuardReport,
    render_summary_md,
    write_report,
    write_synthetic_shock_report,
)
from .run import (
    EXIT_OK,
    RunOptions,
    RunOutcome,
    run_backtest,
)
from .synthetic_shocks import (
    SyntheticShockConfigError,
    most_recent_quarterly_opex,
    resolve_synthetic_shock_dates,
)

__all__ = [
    "ADAPTER_ID",
    "BACKTEST_MODE_ENV",
    "BacktestBroker",
    "BacktestJudgmentLeakError",
    "BacktestLiveBrokerLeakError",
    "BacktestRun",
    "BacktestSummary",
    "CSVDataSource",
    "EXIT_OK",
    "HistoricalDataSource",
    "IngestError",
    "IngestResult",
    "JudgmentStub",
    "KernelGuardReport",
    "OHLCVBar",
    "ReplayClock",
    "ReplayResult",
    "RuleBacktestResult",
    "RunOptions",
    "RunOutcome",
    "SyntheticShockConfigError",
    "SyntheticShockDay",
    "WallClockLeakError",
    "aggregate_metrics",
    "canonicalise_decimal",
    "guard_no_real_llm",
    "ingest_history",
    "max_drawdown_pct",
    "most_recent_quarterly_opex",
    "render_summary_md",
    "replay",
    "resolve_synthetic_shock_dates",
    "run_backtest",
    "sharpe_ratio",
    "total_return_pct",
    "wall_clock_guard",
    "write_report",
    "write_synthetic_shock_report",
]
