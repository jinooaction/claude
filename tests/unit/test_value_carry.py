"""스펙 054 — 밸류(CAPE) 타이밍 + 추세×밸류 분산 이득 측정 단위 테스트.

핵심 불변식: ① CAPE 계산 정확성(손계산 대조) ② 미래 누출 0(노출이 과거 정보만) ③ 노출
범위 [0,1]·비쌀수록 하락 ④ 데이터 부족 시 중립(1.0) ⑤ 결정론.
"""

from __future__ import annotations

from auto_invest.analytics.risk_managed_beta import MonthlyRow
from auto_invest.analytics.value_carry import (
    VERDICT_INSUFFICIENT,
    cape,
    carry_rotation_factors,
    earnings_yield,
    measure_carry_diversification,
    measure_value_diversification,
    real_earnings_deflated,
    value_exposure,
    value_timing_factors,
)


def _row(
    date: str,
    price: float,
    *,
    earnings: float = 2.0,
    cpi: float = 100.0,
    dividend: float = 0.0,
    long_rate: float = 0.0,
) -> MonthlyRow:
    return MonthlyRow(date, price, dividend, long_rate, earnings=earnings, cpi=cpi)


def _series(prices: list[float], *, earnings: float = 2.0, cpi: float = 100.0):
    return [
        _row(f"19{70 + i // 12:02d}-{i % 12 + 1:02d}-01", p, earnings=earnings, cpi=cpi)
        for i, p in enumerate(prices)
    ]


# ──────────────────────────── real_earnings_deflated ────────────────────────────


def test_real_earnings_deflated_basic() -> None:
    rows = [_row("1970-01-01", 100, earnings=4.0, cpi=200.0)]
    assert real_earnings_deflated(rows) == [4.0 / 200.0]


def test_real_earnings_deflated_missing_is_none() -> None:
    rows = [
        _row("1970-01-01", 100, earnings=0.0, cpi=100.0),  # E=0 → None
        _row("1970-02-01", 100, earnings=2.0, cpi=0.0),  # CPI=0 → None
        _row("1970-03-01", 100, earnings=2.0, cpi=100.0),  # 유효
    ]
    assert real_earnings_deflated(rows) == [None, None, 0.02]


# ──────────────────────────────────── cape ────────────────────────────────────


def test_cape_handcomputed() -> None:
    # smooth=2, E=2/CPI=100 고정 → defl=0.02. cape_t=(P_t/100)/0.02.
    rows = _series([100, 110, 120, 130])
    out = cape(rows, smooth_months=2)
    assert out[0] is None and out[1] is None  # 평활창 전
    assert out[2] == (120 / 100) / 0.02  # 60.0
    assert out[3] == (130 / 100) / 0.02  # 65.0


def test_cape_none_when_data_missing() -> None:
    rows = [
        _row("1970-01-01", 100, earnings=2.0, cpi=100.0),
        _row("1970-02-01", 100, earnings=2.0, cpi=100.0),
        _row("1970-03-01", 100, earnings=2.0, cpi=0.0),  # CPI=0 → None
    ]
    out = cape(rows, smooth_months=2)
    assert out[2] is None


def test_cape_smooth_months_validation() -> None:
    import pytest

    with pytest.raises(ValueError, match="smooth_months"):
        cape([], smooth_months=0)


# ─────────────────────────────── value_exposure ───────────────────────────────


def test_value_exposure_length_and_range() -> None:
    rows = _series([100 + i for i in range(200)])
    exp = value_exposure(rows, smooth_months=12, min_history_months=12)
    assert len(exp) == len(rows) - 1
    assert all(0.0 <= e <= 1.0 for e in exp)


def test_value_exposure_neutral_when_insufficient() -> None:
    # 평활창(120) 전 구간은 CAPE=None → 노출 1.0(중립=풀투자).
    rows = _series([100 + i for i in range(50)])
    exp = value_exposure(rows)  # 기본 smooth=120 → 전부 None
    assert all(e == 1.0 for e in exp)


def test_value_exposure_falls_as_expensive() -> None:
    # 가격 지수 상승(E·CPI 고정) → CAPE 단조 증가 → 노출 단조 하락(비쌀수록 축소).
    rows = _series([100, 100, 50, 100, 200, 400, 800])
    exp = value_exposure(rows, smooth_months=2, min_history_months=1)
    # cape: [None,None,25,50,100,200,400] → 단조증가 구간(i=3..6) 노출 하락.
    tail = exp[3:]
    assert tail == sorted(tail, reverse=True)
    assert tail[-1] < tail[0]  # 가장 비쌀 때 < 덜 비쌀 때


def test_value_exposure_no_lookahead() -> None:
    # 핵심: 끝에 데이터를 더 붙여도 앞쪽 노출은 한 톨도 안 바뀐다(확장 윈도우=과거만).
    base = _series([100 + (i % 7) * 13 for i in range(180)])
    extended = base + _series([300, 320, 280, 350])[:4]
    e_short = value_exposure(base, smooth_months=24, min_history_months=12)
    e_long = value_exposure(extended, smooth_months=24, min_history_months=12)
    # base 의 노출(인덱스 0..len(base)-2)은 extended 에서 동일해야 한다.
    for i in range(len(base) - 1):
        assert e_short[i] == e_long[i], f"index {i} leaked future"


# ─────────────────────────── value_timing_factors ───────────────────────────


def test_value_timing_factors_length() -> None:
    rows = _series([100 + i for i in range(150)])
    f = value_timing_factors(rows, smooth_months=24, min_history_months=12)
    assert len(f) == len(rows) - 1
    assert all(x > 0 for x in f)  # 그로스 팩터는 양수


def test_value_timing_full_exposure_equals_market() -> None:
    # 노출이 전부 1.0(평활창 전)이면 밸류 팩터 == 단순 보유 시장 팩터.
    from auto_invest.analytics.risk_managed_beta import market_total_return_factors

    rows = _series([100 + i for i in range(50)])  # smooth=120 전 → 노출 1.0
    f = value_timing_factors(rows)
    assert f == market_total_return_factors(rows)


# ─────────────────────── measure_value_diversification ───────────────────────


def test_measure_diversification_shape() -> None:
    rows = _series([100 + (i % 5) * 7 + i * 0.3 for i in range(200)])
    stats = measure_value_diversification(
        rows, window=10, smooth_months=24, min_history_months=12
    )
    d = stats.as_dict()
    assert {
        "verdict",
        "candidate_label",
        "trend",
        "candidate",
        "combined",
        "buy_hold",
        "correlation",
    } <= d.keys()
    assert stats.combined.n_months == len(rows) - 1
    assert stats.candidate_label == "밸류(CAPE)"


def test_measure_diversification_deterministic() -> None:
    rows = _series([100 + (i % 9) * 11 for i in range(160)])
    a = measure_value_diversification(rows, smooth_months=24, min_history_months=12)
    b = measure_value_diversification(rows, smooth_months=24, min_history_months=12)
    assert a.as_dict() == b.as_dict()


def test_measure_diversification_insufficient() -> None:
    rows = _series([100, 101])  # 표본 1 → 결합 샤프 정의 불가
    stats = measure_value_diversification(rows, smooth_months=1, min_history_months=1)
    assert stats.verdict == VERDICT_INSUFFICIENT


def test_blend_weight_validation() -> None:
    import pytest

    rows = _series([100 + i for i in range(40)])
    with pytest.raises(ValueError, match="blend_weight"):
        measure_value_diversification(rows, blend_weight=1.5)


# ─────────────────────────────── 캐리(자산 선택) ───────────────────────────────


def test_earnings_yield_basic_and_missing() -> None:
    rows = [
        _row("1970-01-01", 100, earnings=5.0),  # E/P = 0.05
        _row("1970-02-01", 100, earnings=0.0),  # E=0 → None
    ]
    assert earnings_yield(rows) == [0.05, None]


def test_carry_rotation_holds_equity_when_ep_beats_rate() -> None:
    # E/P 0.05 > 금리 0.03 → 주식 보유 → 주식 총수익(110/100=1.1) 그대로.
    rows = [
        _row("1970-01-01", 100, earnings=5.0, long_rate=3.0),
        _row("1970-02-01", 110, earnings=5.0, long_rate=3.0),
    ]
    f = carry_rotation_factors(rows)
    assert len(f) == 1
    assert abs(f[0] - 1.1) < 1e-9


def test_carry_rotation_holds_bond_when_rate_beats_ep() -> None:
    # E/P 0.02 < 금리 0.08 → 채권 보유 → 주식 급등(1.3) 안 따라간다.
    rows = [
        _row("1970-01-01", 100, earnings=2.0, long_rate=8.0),
        _row("1970-02-01", 130, earnings=2.0, long_rate=8.0),
    ]
    f = carry_rotation_factors(rows)
    assert len(f) == 1
    assert 0.0 < f[0] < 1.3  # 채권이라 주식 급등 미반영


def test_measure_carry_shape() -> None:
    rows = [
        _row(
            f"19{70 + i // 12:02d}-{i % 12 + 1:02d}-01",
            100 + i + (i % 6) * 4,
            earnings=4.0 + (i % 3),
            long_rate=2.0 + (i % 5),
        )
        for i in range(160)
    ]
    stats = measure_carry_diversification(rows, window=10)
    assert stats.candidate_label == "캐리(E/P vs 금리)"
    assert stats.combined.n_months == len(rows) - 1
    assert {"candidate", "candidate_label"} <= stats.as_dict().keys()
