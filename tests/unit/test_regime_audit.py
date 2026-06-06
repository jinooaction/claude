"""스펙 045 — 최근 regime / 시점 강건성 감사 단위 테스트."""

from __future__ import annotations

import math

from auto_invest.analytics.regime_audit import (
    correlation_regime,
    factor_year,
    rolling_correlation_series,
    slice_by_year,
    stress_year,
    window_stats,
    year_cumulative_return_pct,
)
from auto_invest.analytics.risk_managed_beta import MonthlyRow


def _rows_years(year_counts: list[tuple[int, int]], *, rate: float = 4.0) -> list[MonthlyRow]:
    """[(year, n_months), ...] → 월 행들(가격 완만 상승)."""
    rows: list[MonthlyRow] = []
    price = 100.0
    for year, n in year_counts:
        for m in range(n):
            price *= 1.005
            rows.append(MonthlyRow(date=f"{year:04d}-{1 + m % 12:02d}-01", price=price,
                                   dividend=0.0, long_rate=rate))
    return rows


def test_factor_year_maps_to_next_row():
    rows = _rows_years([(2001, 3), (2002, 2)])
    # factor index i 는 rows[i+1] 에서 실현.
    assert factor_year(rows, 0) == 2001  # rows[1]
    assert factor_year(rows, 2) == 2002  # rows[3]


def test_slice_by_year_selects_realization_year():
    rows = _rows_years([(2001, 12), (2002, 12)])
    factors = [1.01] * (len(rows) - 1)  # 길이 23
    only_2002 = slice_by_year(rows, factors, 2002, 2002)
    # rows[i+1] 가 2002 인 것 = i+1>=12 → i>=11 → 12개.
    assert len(only_2002) == 12
    both = slice_by_year(rows, factors, 2001, 2002)
    assert len(both) == 23


def test_year_cumulative_return_pct():
    rows = _rows_years([(2001, 1), (2002, 12)])
    factors = [1.01] * (len(rows) - 1)
    # 2002 실현 팩터 12개(모두 1.01) → 1.01^12 - 1.
    got = year_cumulative_return_pct(rows, factors, 2002)
    assert abs(got - ((1.01 ** 12 - 1.0) * 100.0)) < 1e-6


def test_rolling_correlation_series_length_and_range():
    a = [1.0 + 0.01 * (i % 5) for i in range(50)]
    b = [1.0 + 0.01 * ((i + 2) % 5) for i in range(50)]
    series = rolling_correlation_series(a, b, 12)
    assert len(series) == 50 - 12 + 1
    for c in series:
        assert -1.0 <= c <= 1.0


def test_rolling_correlation_perfect_positive():
    a = [1.0 + 0.001 * i for i in range(30)]
    b = [1.0 + 0.002 * i for i in range(30)]  # 같은 방향 선형
    series = rolling_correlation_series(a, b, 12)
    assert all(abs(c - 1.0) < 1e-6 for c in series)


def test_correlation_regime_structure():
    rows = _rows_years([(y, 12) for y in range(2000, 2010)])
    reg = correlation_regime(rows, window=36)
    d = reg.as_dict()
    assert d["window_months"] == 36
    assert d["current"] is None or -1.0 <= d["current"] <= 1.0
    assert d["recent_5y_pos_fraction"] is None or 0.0 <= d["recent_5y_pos_fraction"] <= 1.0


def test_window_stats_structure_and_months():
    rows = _rows_years([(y, 12) for y in range(1990, 2001)])
    ws = window_stats(rows, "1990년대", 1990, 1999, window=10)
    d = ws.as_dict()
    assert d["label"] == "1990년대"
    assert d["n_months"] > 0
    for key in ("bh_6040", "trend_equity", "diversified"):
        assert math.isfinite(d[key]["sharpe"])


def test_stress_year_returns_four_strategies():
    rows = _rows_years([(y, 12) for y in range(2018, 2024)])
    sy = stress_year(rows, 2022, window=10)
    d = sy.as_dict()
    assert d["year"] == 2022
    for key in ("bh_equity_pct", "bh_6040_pct", "trend_equity_pct", "diversified_pct"):
        assert isinstance(d[key], float)
