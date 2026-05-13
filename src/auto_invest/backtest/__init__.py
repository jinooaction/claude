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
