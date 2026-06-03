"""스펙 034 — 체계적 유니버스 구성(유동성 기반) 테스트.

SC-U01: 동일 일봉 → 동일 유니버스(결정론).
SC-U02: 유동성 순위가 달러 거래대금 내림차순(높은 종목 우선).
SC-U03: 최소 이력·최소 유동성 미달 종목은 구성에서 제외.
(중앙값 vs 평균: 한 번의 비정상 거래량이 thin 종목을 끌어올리지 못함.)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from auto_invest.market_data.store import PriceBar
from auto_invest.strategy.universe import (
    liquidity_rank,
    median_dollar_volume,
    select_universe,
)

# =========================================================================== #
# helpers                                                                      #
# =========================================================================== #


def _make_bars(
    symbol: str, closes: list[float], volumes: list[int] | None = None
) -> list[PriceBar]:
    base = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)
    vols = volumes if volumes is not None else [1000] * len(closes)
    bars: list[PriceBar] = []
    for i, (c, v) in enumerate(zip(closes, vols, strict=True)):
        ts = (base + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        p = Decimal(str(c))
        bars.append(
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=ts,
                open_usd=p,
                high_usd=p,
                low_usd=p,
                close_usd=p,
                volume=v,
            )
        )
    return bars


# =========================================================================== #
# median_dollar_volume                                                         #
# =========================================================================== #


def test_median_dollar_volume_odd_count() -> None:
    # closes 10/20/30 with volume 100 → dollar vols 1000/2000/3000 → median 2000.
    bars = _make_bars("AAA", [10, 20, 30], [100, 100, 100])
    assert median_dollar_volume(bars, lookback_bars=60) == Decimal("2000.00")


def test_median_dollar_volume_even_count_averages_two_middle() -> None:
    # dollar vols 1000/2000/3000/4000 → median = (2000+3000)/2 = 2500.
    bars = _make_bars("AAA", [10, 20, 30, 40], [100, 100, 100, 100])
    assert median_dollar_volume(bars, lookback_bars=60) == Decimal("2500.00")


def test_median_ignores_single_abnormal_print() -> None:
    # A single huge-volume spike must NOT promote an otherwise-thin name: the
    # median stays low while the mean would explode. dollar vols
    # 100/100/100/100/1_000_000 → median 100 (mean would be ~200_080).
    bars = _make_bars("THIN", [1, 1, 1, 1, 1], [100, 100, 100, 100, 1_000_000])
    assert median_dollar_volume(bars, lookback_bars=60) == Decimal("100.00")


def test_median_dollar_volume_lookback_window() -> None:
    # Only the most-recent N bars count. Old thin bars are excluded.
    bars = _make_bars("AAA", [1, 1, 10, 10], [1, 1, 100, 100])  # dvols 1,1,1000,1000
    assert median_dollar_volume(bars, lookback_bars=2) == Decimal("1000.00")


def test_median_dollar_volume_no_bars_returns_none() -> None:
    assert median_dollar_volume([], lookback_bars=60) is None


# =========================================================================== #
# liquidity_rank — SC-U02                                                      #
# =========================================================================== #


def test_liquidity_rank_orders_by_dollar_volume_desc() -> None:
    symbol_bars = {
        "LOW": _make_bars("LOW", [10, 10, 10], [10, 10, 10]),      # mdv 100
        "HIGH": _make_bars("HIGH", [10, 10, 10], [1000, 1000, 1000]),  # mdv 10000
        "MID": _make_bars("MID", [10, 10, 10], [100, 100, 100]),   # mdv 1000
    }
    ranked = liquidity_rank(symbol_bars, lookback_bars=60)
    assert [s for s, _ in ranked] == ["HIGH", "MID", "LOW"]


def test_liquidity_rank_data_poor_symbols_sort_last() -> None:
    symbol_bars = {
        "REAL": _make_bars("REAL", [10, 10], [100, 100]),  # mdv 1000
        "EMPTY": [],  # sentinel → last
    }
    ranked = liquidity_rank(symbol_bars, lookback_bars=60)
    assert ranked[0][0] == "REAL"
    assert ranked[-1][0] == "EMPTY"
    assert ranked[-1][1] < 0  # sentinel


def test_liquidity_rank_ties_break_by_symbol_name() -> None:
    symbol_bars = {
        "BBB": _make_bars("BBB", [10, 10], [100, 100]),
        "AAA": _make_bars("AAA", [10, 10], [100, 100]),
    }
    ranked = liquidity_rank(symbol_bars, lookback_bars=60)
    assert [s for s, _ in ranked] == ["AAA", "BBB"]  # equal mdv → alpha order


# =========================================================================== #
# select_universe — SC-U01 / SC-U03                                           #
# =========================================================================== #


def test_select_universe_top_n_most_liquid() -> None:
    symbol_bars = {
        "A": _make_bars("A", [10] * 5, [10] * 5),       # mdv 100
        "B": _make_bars("B", [10] * 5, [1000] * 5),     # mdv 10000
        "C": _make_bars("C", [10] * 5, [100] * 5),      # mdv 1000
        "D": _make_bars("D", [10] * 5, [5] * 5),        # mdv 50
    }
    # Top-2 by liquidity = B, C; returned alphabetically.
    assert select_universe(symbol_bars, top_n=2, lookback_bars=60) == ["B", "C"]


def test_select_universe_min_history_filters_short_symbols() -> None:
    symbol_bars = {
        "LONG": _make_bars("LONG", [10] * 10, [1000] * 10),
        "SHORT": _make_bars("SHORT", [10] * 3, [9999] * 3),  # very liquid but tiny history
    }
    # SHORT is the most liquid but fails the history floor → excluded.
    out = select_universe(
        symbol_bars, top_n=5, min_history_bars=5, lookback_bars=60
    )
    assert out == ["LONG"]


def test_select_universe_min_dollar_volume_floor() -> None:
    symbol_bars = {
        "LIQUID": _make_bars("LIQUID", [10] * 5, [1000] * 5),  # mdv 10000
        "THIN": _make_bars("THIN", [10] * 5, [1] * 5),          # mdv 10
    }
    out = select_universe(
        symbol_bars, top_n=5, min_dollar_volume=Decimal("100"), lookback_bars=60
    )
    assert out == ["LIQUID"]


def test_select_universe_deterministic() -> None:
    # SC-U01: identical input → identical output, repeatedly.
    symbol_bars = {
        "A": _make_bars("A", [10] * 5, [300] * 5),
        "B": _make_bars("B", [10] * 5, [200] * 5),
        "C": _make_bars("C", [10] * 5, [100] * 5),
    }
    first = select_universe(symbol_bars, top_n=2, lookback_bars=60)
    for _ in range(5):
        assert select_universe(symbol_bars, top_n=2, lookback_bars=60) == first
    assert first == ["A", "B"]


def test_select_universe_empty_when_nothing_eligible() -> None:
    symbol_bars = {"X": _make_bars("X", [10] * 3, [1] * 3)}
    out = select_universe(
        symbol_bars,
        top_n=5,
        min_history_bars=100,
        min_dollar_volume=Decimal("1000000"),
        lookback_bars=60,
    )
    assert out == []
