"""Market data quality checks (FR-017).

A rule is "armed" — eligible for trigger evaluation — only when its
underlying market-data feed is healthy. Two checks compose health:

  * Recency:    the latest bar is no older than `max_staleness`.
  * Continuity: the most recent bars are at the expected cadence;
                a missed bar implies a gap.

Indicator-based rules also need a minimum bar count (`min_bars`)
before they can fire; that's the third state, INSUFFICIENT_DATA.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from auto_invest.market_data.store import PriceBar


class QualityState(StrEnum):
    ARMED = "ARMED"
    STALE = "STALE"
    GAP = "GAP"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class QualityReport:
    state: QualityState
    detail: str | None = None


_PERIOD_MAP: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def expected_period(timeframe: str) -> timedelta:
    if timeframe not in _PERIOD_MAP:
        raise ValueError(f"unsupported timeframe: {timeframe!r}")
    return _PERIOD_MAP[timeframe]


def _parse_iso(text: str) -> datetime:
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def assess_quality(
    bars: list[PriceBar],
    *,
    timeframe: str,
    now: datetime,
    max_staleness: timedelta | None = None,
    min_bars: int = 1,
) -> QualityReport:
    """Classify the current state of a market-data feed.

    `bars` MUST be in ascending bar_open_utc order.
    """
    if len(bars) < min_bars:
        return QualityReport(
            state=QualityState.INSUFFICIENT_DATA,
            detail=f"have {len(bars)} bars, need {min_bars}",
        )

    period = expected_period(timeframe)
    if max_staleness is None:
        # Tolerate a single missed bar by default.
        max_staleness = period * 2

    latest = _parse_iso(bars[-1].bar_open_utc)
    if now - latest > max_staleness:
        return QualityReport(
            state=QualityState.STALE,
            detail=(f"latest bar {bars[-1].bar_open_utc} older than max_staleness={max_staleness}"),
        )

    tolerance = period / 10
    for prev, curr in zip(bars, bars[1:], strict=False):
        gap = _parse_iso(curr.bar_open_utc) - _parse_iso(prev.bar_open_utc)
        if abs(gap - period) > tolerance:
            return QualityReport(
                state=QualityState.GAP,
                detail=(
                    f"unexpected gap between {prev.bar_open_utc} and "
                    f"{curr.bar_open_utc}: {gap} (expected {period})"
                ),
            )

    return QualityReport(state=QualityState.ARMED)
