"""Spec 011 — 라이브 성과 측정 하네스 (읽기 전용).

audit_log의 체결(라이브 FILL / 페이퍼 ORDER_PAPER_FILLED)에서 실현 손익을
재구성하고, 미청산 포지션을 주입된 현재 시세로 평가해 미실현 손익을 더한다.
DB에 어떤 row도 쓰지 않는다. 위험조정 지표는 spec 008 backtest/metrics.py 를
재사용한다.
"""

from auto_invest.performance.engine import (
    FillRecord,
    PerformanceReport,
    PositionState,
    RulePerformance,
    SymbolPerformance,
    build_performance_report,
    compute_performance,
    read_fills,
    reconstruct,
    render_text,
)

__all__ = [
    "FillRecord",
    "PerformanceReport",
    "PositionState",
    "RulePerformance",
    "SymbolPerformance",
    "build_performance_report",
    "compute_performance",
    "read_fills",
    "reconstruct",
    "render_text",
]
