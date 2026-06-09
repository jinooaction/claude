"""스펙 048 — 다중 추세 속도 앙상블 단위 테스트. 순수·결정론·미래 누출 0 을 못박는다."""

from __future__ import annotations

import math

from auto_invest.analytics.risk_managed_beta import LegStats, MonthlyRow
from auto_invest.analytics.trend_ensemble import (
    _classify_ensemble,
    _risk_parity_combine,
    compare_trend_ensemble,
    ensemble_global_factors,
    ensemble_in_fraction,
    ensemble_sleeve_factors,
)


def _rows(prices, *, div=0.0, rate=4.0):
    return [
        MonthlyRow(date=f"20{1 + i // 12:02d}-{1 + i % 12:02d}-01", price=p,
                   dividend=div, long_rate=rate)
        for i, p in enumerate(prices)
    ]


def _gold(rows, prices):
    return [p for p in prices][: len(rows)]


# ─────────────────────────── 분수 신호 ───────────────────────────


def test_ensemble_fraction_single_window_is_binary():
    # windows=(w,) 이면 0/1 만 나온다(단일 속도와 동일).
    levels = [10, 11, 12, 13, 9, 8, 14]
    f = ensemble_in_fraction(levels, (3,))
    assert all(x in (0.0, 1.0) for x in f)
    assert len(f) == len(levels) - 1


def test_ensemble_fraction_sustained_drop_exits():
    # 지속 하락 뒤엔 분수가 1 미만으로 떨어진다(급락 *기간* 신호는 급락 이전 값만 보므로 —
    # 미래 누출 0 — 하락이 이어진 뒤에야 반영). 단조 데이터는 모든 속도가 같이 뒤집힌다.
    levels = [100, 101, 102, 103, 104, 105, 106, 50, 40, 30, 25]
    f = ensemble_in_fraction(levels, (2, 4, 6))
    assert all(0.0 <= x <= 1.0 for x in f)
    assert min(f) < 1.0

def test_ensemble_fraction_intermediate_when_speeds_disagree():
    # V자: 빠른(2개월)은 회복을 추세 위로 보고, 느린(4개월)은 아직 추세 아래 → 분수 0.5.
    levels = [10, 9, 8, 7, 8, 9, 10]
    f = ensemble_in_fraction(levels, (2, 4))
    assert any(0.0 < x < 1.0 for x in f)  # 속도 불일치 → 중간 분수


def test_ensemble_fraction_insufficient_sma_is_in_market():
    # 초반(SMA 미정)엔 투자(1.0)로 둔다(단일 속도 규칙과 동일).
    levels = [10, 11, 12]
    f = ensemble_in_fraction(levels, (10,))  # window > 데이터 → 항상 미정
    assert f == [1.0, 1.0]


def test_ensemble_fraction_no_lookahead():
    # 뒤 값을 바꿔도 앞 분수는 불변(미래 누출 0).
    base = [10, 11, 12, 13, 14, 15, 16]
    a = ensemble_in_fraction(base, (3,))
    b = ensemble_in_fraction(base[:-1] + [999], (3,))
    assert a[:-1] == b[:-1]


# ─────────────────────────── 슬리브 ───────────────────────────


def test_ensemble_sleeve_blends_asset_and_cash():
    asset = [1.05, 1.10, 0.90]
    cash = [1.00, 1.00, 1.00]
    frac = [1.0, 0.5, 0.0]
    s = ensemble_sleeve_factors(asset, cash, frac)
    assert math.isclose(s[0], 1.05)            # fraction 1 → 자산
    assert math.isclose(s[1], 0.5 * 1.10 + 0.5 * 1.00)  # 절반
    assert math.isclose(s[2], 1.00)            # fraction 0 → 현금


# ─────────────────────────── 역변동성 결합 ───────────────────────────


def test_risk_parity_combine_determinism_and_length():
    s1 = [1.01, 0.99, 1.02, 0.98, 1.03, 0.97] * 4
    s2 = [1.001, 1.002, 0.999, 1.0, 1.001, 0.998] * 4
    a = _risk_parity_combine([s1, s2], vol_window=6)
    b = _risk_parity_combine([s1, s2], vol_window=6)
    assert a == b and len(a) == len(s1)


def test_risk_parity_combine_downweights_high_vol():
    # 고변동 슬리브가 결합 변동성에 덜 기여 → 결합 변동성 < 단순 평균 변동성.
    n = 48
    hi = [1.0 + (0.20 if i % 2 == 0 else -0.20) for i in range(n)]   # 큰 변동
    lo = [1.0 + (0.002 if i % 3 == 0 else -0.001) for i in range(n)]  # 작은 변동

    def vol(fs):
        r = [f - 1 for f in fs]
        m = sum(r) / len(r)
        return (sum((x - m) ** 2 for x in r) / (len(r) - 1)) ** 0.5

    rp = _risk_parity_combine([hi, lo], vol_window=12)
    eq = [0.5 * hi[i] + 0.5 * lo[i] for i in range(n)]
    assert vol(rp) < vol(eq)  # 역변동성이 고변동을 덜 담아 결합 변동성↓


# ─────────────────────────── 비교 / 분류 ───────────────────────────


def test_compare_single_vs_ensemble_structure_and_determinism():
    prices = [100 + i + 5 * math.sin(i / 4) for i in range(80)]
    rows = _rows(prices, div=1.0)
    gl = _gold(rows, [60 + 4 * math.sin(i / 3) + i * 0.2 for i in range(80)])
    a = compare_trend_ensemble(rows, gl, single_window=10, ensemble_windows=(6, 10, 12))
    b = compare_trend_ensemble(rows, gl, single_window=10, ensemble_windows=(6, 10, 12))
    assert a.as_dict() == b.as_dict()
    assert a.verdict in ("TREND_ENSEMBLE_EDGE", "NO_ENSEMBLE_BENEFIT", "INSUFFICIENT")


def test_compare_single_window_ensemble_equals_single():
    # ensemble_windows=(single,) 이면 단일과 앙상블이 동일(같은 경로) → 개선 0.
    prices = [100 + i for i in range(60)]
    rows = _rows(prices, div=1.0)
    gl = _gold(rows, [50 + i for i in range(60)])
    cmp = compare_trend_ensemble(rows, gl, single_window=10, ensemble_windows=(10,))
    assert cmp.single_speed.as_dict() == cmp.ensemble.as_dict()


def _leg(sharpe, calmar, dd):
    return LegStats(5.0, 10.0, sharpe, dd, calmar, 0.9, 1.0, 120)


def test_classify_ensemble_edge_requires_all_three():
    v, _ = _classify_ensemble(_leg(1.8, 1.7, 5.3), _leg(2.0, 2.2, 3.7))
    assert v == "TREND_ENSEMBLE_EDGE"


def test_classify_ensemble_no_benefit_when_drawdown_worse():
    v, reason = _classify_ensemble(_leg(1.6, 1.1, 5.3), _leg(1.7, 1.2, 5.7))
    assert v == "NO_ENSEMBLE_BENEFIT" and "낙폭 악화" in reason


def test_ensemble_global_factors_length():
    rows = _rows([100 + i for i in range(40)], div=1.0)
    gl = _gold(rows, [50 + i for i in range(40)])
    f = ensemble_global_factors(rows, gl, ensemble_windows=(3, 6, 9, 12))
    assert len(f) == len(rows) - 1
