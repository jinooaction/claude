"""Spec 011 — 라이브 성과 측정 하네스 (읽기 전용).

audit_log의 체결(라이브 FILL / 페이퍼 ORDER_PAPER_FILLED)에서 실현 손익을
재구성하고, 미청산 포지션을 주입된 현재 시세로 평가해 미실현 손익을 더한다.
DB에 어떤 row도 쓰지 않는다. 위험조정 지표는 spec 008 backtest/metrics.py 를
재사용한다.
"""

from auto_invest.performance.engine import (
    FillLatencyStats,
    FillRecord,
    PerformanceReport,
    PositionState,
    RulePerformance,
    SymbolPerformance,
    build_performance_report,
    compute_fill_latency,
    compute_performance,
    compute_slippage,
    read_fills,
    reconstruct,
    render_latency_text,
    render_slippage_text,
    render_text,
)

__all__ = [
    "FillLatencyStats",
    "FillRecord",
    "PerformanceReport",
    "PositionState",
    "RulePerformance",
    "SymbolPerformance",
    "build_performance_report",
    "compute_fill_latency",
    "compute_performance",
    "compute_slippage",
    "read_fills",
    "reconstruct",
    "render_latency_text",
    "render_slippage_text",
    "render_text",
]
