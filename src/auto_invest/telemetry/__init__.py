"""LLM token telemetry — spec 002.

Public surface:
    TokenMeter      — async context manager wrapping every Anthropic call
    TokenUsage      — in-memory record of one metered call
    PriceTable      — model → USD/token loader
    TierTable       — KPI threshold loader
    compute_snapshot — KPI aggregation over a time window
    integrity_check — startup audit for token_usage / LLM_CALL pairing
"""

from auto_invest.telemetry.kpi import KPI, EfficiencySnapshot, compute_snapshot
from auto_invest.telemetry.meter import TokenMeter
from auto_invest.telemetry.prices import PriceTable, load_prices
from auto_invest.telemetry.store import TokenUsage, append_token_usage, integrity_check
from auto_invest.telemetry.thresholds import TierTable, load_thresholds

__all__ = [
    "EfficiencySnapshot",
    "KPI",
    "PriceTable",
    "TierTable",
    "TokenMeter",
    "TokenUsage",
    "append_token_usage",
    "compute_snapshot",
    "integrity_check",
    "load_prices",
    "load_thresholds",
]
